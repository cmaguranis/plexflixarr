import logging

from src.clients.anilist_client import AniListClient
from src.clients.anime_list_client import resolve_tmdb_id
from src.clients.plex_client import PlexClient
from src.clients.tmdb_client import TmdbClient
from src.clients.trakt_client import TraktClient
from src.config import Settings
from src.ingestion.shared import (
    MediaItem,
    _dedup_by_tmdb_id,
    _from_tmdb_item,
    filter_media,
    label_discover_items,
    write_dummies,
)
from src.jobs.schedule import Schedule
from src.jobs.state import CallState

logger = logging.getLogger(__name__)

_INGEST_SCHEDULE_PATH = "scripts/ingest_schedule.json"


def fetch_media(config: Settings) -> list[MediaItem]:
    """Step 1: Fetch raw candidates from TMDB, Trakt, and AniList."""
    items: list[MediaItem] = []

    tmdb = TmdbClient(config)

    logger.info("Fetching TMDB streaming content...")
    _before = len(items)
    items.extend(_from_tmdb_item(i) for i in tmdb.fetch_streaming(config.PAGES_PER_PROVIDER))
    logger.info("  → %d items", len(items) - _before)

    logger.info("Fetching TMDB trending content...")
    _before = len(items)
    items.extend(_from_tmdb_item(i) for i in tmdb.fetch_trending(config.PAGES_PER_PROVIDER))
    logger.info("  → %d items", len(items) - _before)

    trakt = TraktClient(config)

    logger.info("Fetching Trakt recommendations...")
    _before = len(items)
    for item in trakt.fetch_recommendations(config.TRAKT_USERNAME):
        items.append(
            MediaItem(
                title=item.title,
                year=item.year,
                media_type=item.media_type,
                labels=["Discover_Recs"],
                tmdb_id=item.tmdb_id,
            )
        )
    logger.info("  → %d items", len(items) - _before)

    if config.TRAKT_USERNAME:
        logger.info("Fetching Couchmoney themed lists for %s...", config.TRAKT_USERNAME)
        _before = len(items)
        for trakt_list in trakt.fetch_couchmoney_lists(config.TRAKT_USERNAME):
            for item in trakt_list.items:
                items.append(
                    MediaItem(
                        title=item.title,
                        year=item.year,
                        media_type=item.media_type,
                        labels=["Discover_Recs"],
                        tmdb_id=item.tmdb_id,
                    )
                )
        logger.info("  → %d items", len(items) - _before)

    anilist = AniListClient(config)

    logger.info("Fetching AniList trending anime...")
    _before = len(items)
    for item in anilist.fetch_trending():
        items.append(
            MediaItem(
                title=item.title,
                year=item.year,
                media_type=item.media_type,
                labels=["Discover_Anime"],
                anilist_id=item.anilist_id,
            )
        )
    logger.info("  → %d items", len(items) - _before)

    if config.ANILIST_USERNAME:
        logger.info("Fetching AniList recommendations for %s...", config.ANILIST_USERNAME)
        _before = len(items)
        for item in anilist.fetch_recommendations(config.ANILIST_USERNAME):
            items.append(
                MediaItem(
                    title=item.title,
                    year=item.year,
                    media_type=item.media_type,
                    labels=["Discover_Anime"],
                    anilist_id=item.anilist_id,
                )
            )
        logger.info("  → %d items", len(items) - _before)

    # Resolve AniList IDs to TMDb IDs so folders get {tmdb-N} names and dedup works across sources
    for item in items:
        if item.anilist_id is not None and item.tmdb_id is None:
            item.tmdb_id = resolve_tmdb_id(item.anilist_id)

    # Merge labels for duplicate tmdb_ids; keep Trakt items that have no tmdb_id
    deduped = _dedup_by_tmdb_id(items, merge_labels=True, keep_unresolved=True)

    logger.info("Fetched %d candidates (%d after dedup).", len(items), len(deduped))
    return deduped


def run(config: Settings | None = None) -> None:
    config = config or Settings()

    sched = Schedule(_INGEST_SCHEDULE_PATH)
    if not sched.is_enabled():
        logger.info("Ingestion schedule is disabled — exiting.")
        return

    items = fetch_media(config)
    filtered = filter_media(items, config)
    write_dummies(filtered, config)

    plex = PlexClient(config)
    logger.info("Triggering Plex library scans...")
    plex.refresh_and_wait(config.DISCOVER_MOVIES_LIB, config.DISCOVER_SHOWS_LIB)

    label_discover_items(filtered, plex, config)

    CallState(config.STATE_FILE).record("ingestion")
    logger.info("Ingestion complete.")


def run_with_dedupe(config: Settings | None = None) -> None:
    from src.discover import dedupe

    run(config)
    dedupe.run()
