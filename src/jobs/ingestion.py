import logging
import time
from dataclasses import dataclass, field

from src.clients.anilist_client import AniListClient
from src.clients.mdblist_client import MdblistClient
from src.clients.plex_client import PlexClient
from src.clients.tmdb_client import TmdbClient
from src.clients.trakt_client import TraktClient, TraktList
from src.config import Settings
from src.dummy import create_dummy, ensure_template
from src.jobs import kometa_config
from src.jobs.schedule import Schedule

logger = logging.getLogger(__name__)

_MDBLIST_RATE_DELAY = 1  # seconds between MDBList lookup calls (free tier: 1,000/day)
_INGEST_SCHEDULE_PATH = "scripts/ingest_schedule.json"
_DISCOVER_MOVIES_LIB = "Discover Movies"
_DISCOVER_SHOWS_LIB = "Discover Shows"


@dataclass
class MediaItem:
    title: str
    year: str | None
    media_type: str
    labels: list[str] = field(default_factory=list)
    tmdb_id: int | None = None  # None for Trakt items; MDBList quality check is skipped
    genre_ids: list[int] = field(default_factory=list)


def fetch_media(config: Settings) -> tuple[list[MediaItem], list[TraktList]]:
    """
    Step 1: Fetch raw candidates from TMDB and Trakt.

    Returns a tuple of:
      - deduped MediaItem list for the ingestion pipeline
      - TraktList list for Kometa config generation (Couchmoney themed rows)
    """
    items: list[MediaItem] = []

    tmdb = TmdbClient(config)

    logger.info("Fetching TMDB streaming content...")
    for item in tmdb.fetch_streaming(config.PAGES_PER_PROVIDER):
        items.append(MediaItem(
            title=item.title, year=item.year, media_type=item.media_type, tmdb_id=item.tmdb_id,
            genre_ids=item.genre_ids,
            labels=item.labels + _genre_labels(item.genre_ids, config),
        ))

    logger.info("Fetching TMDB trending content...")
    for item in tmdb.fetch_trending(config.PAGES_PER_PROVIDER):
        items.append(MediaItem(
            title=item.title, year=item.year, media_type=item.media_type, tmdb_id=item.tmdb_id,
            genre_ids=item.genre_ids,
            labels=item.labels + _genre_labels(item.genre_ids, config),
        ))

    trakt = TraktClient(config)

    logger.info("Fetching Trakt recommendations...")
    for item in trakt.fetch_recommendations():
        items.append(
            MediaItem(
                title=item.title,
                year=item.year,
                media_type=item.media_type,
                labels=["Discover_Recs"],
            )
        )

    # Fetch Couchmoney themed lists (requires TRAKT_USERNAME)
    themed_lists: list[TraktList] = []
    if config.TRAKT_USERNAME:
        logger.info("Fetching Couchmoney themed lists for %s...", config.TRAKT_USERNAME)
        themed_lists = trakt.fetch_couchmoney_lists(config.TRAKT_USERNAME)
        for trakt_list in themed_lists:
            for item in trakt_list.items:
                items.append(MediaItem(
                    title=item.title,
                    year=item.year,
                    media_type=item.media_type,
                    labels=[trakt_list.label],
                ))

    anilist = AniListClient(config)

    logger.info("Fetching AniList trending anime...")
    for item in anilist.fetch_trending():
        items.append(MediaItem(
            title=item.title,
            year=item.year,
            media_type=item.media_type,
            labels=["Discover_Anime"],
        ))

    # Fetch AniList personalised anime recommendations (requires ANILIST_USERNAME)
    if config.ANILIST_USERNAME:
        logger.info("Fetching AniList recommendations for %s...", config.ANILIST_USERNAME)
        for item in anilist.fetch_recommendations(config.ANILIST_USERNAME):
            items.append(MediaItem(
                title=item.title,
                year=item.year,
                media_type=item.media_type,
                labels=["Discover_Anime"],
            ))

    # Merge labels for duplicate tmdb_ids (same title appearing in multiple sources)
    merged: dict[int, MediaItem] = {}
    for item in items:
        if item.tmdb_id is None:
            continue
        if item.tmdb_id in merged:
            existing = merged[item.tmdb_id]
            existing.labels = list(dict.fromkeys(existing.labels + item.labels))
        else:
            merged[item.tmdb_id] = item
    # Trakt items have no tmdb_id — append them as-is
    trakt_items = [i for i in items if i.tmdb_id is None]
    deduped = list(merged.values()) + trakt_items

    logger.info("Fetched %d candidates (%d after dedup).", len(items), len(deduped))
    return deduped, themed_lists


def filter_media(items: list[MediaItem], config: Settings) -> list[MediaItem]:
    """Step 2: Remove low-quality titles and those already owned in real Plex libraries."""
    mdblist = MdblistClient(config)
    plex = PlexClient(config)
    filtered: list[MediaItem] = []

    for item in items:
        # TMDB items carry a tmdb_id; Trakt items are already personalised, skip quality gate
        if item.tmdb_id is not None:
            if not mdblist.passes_quality_check(item.tmdb_id, item.media_type):
                logger.debug("Rejected (quality): %s", item.title)
                continue
            time.sleep(_MDBLIST_RATE_DELAY)

        real_libs = (
            config.REAL_MOVIES_LIBS
            if item.media_type in ("movie", "movies")
            else config.REAL_SHOWS_LIBS
        )
        if plex.exists_in_any(real_libs, item.title, item.media_type):
            logger.debug("Already in real library, skipping: %s", item.title)
            continue

        filtered.append(item)

    logger.info("%d items passed filters.", len(filtered))
    return filtered


def write_dummies(items: list[MediaItem], config: Settings) -> None:
    """Step 3: Create dummy .mkv files, trigger Plex scan, and apply labels."""
    ensure_template(config.TEMPLATE_FILE)
    tagged: list[MediaItem] = []

    for item in items:
        if create_dummy(item.title, item.year, item.media_type, config):
            tagged.append(item)

    if not tagged:
        logger.info("No new dummy files created.")
        return

    plex = PlexClient(config)
    logger.info("Triggering Plex library scans...")
    plex.refresh_and_wait(_DISCOVER_MOVIES_LIB, _DISCOVER_SHOWS_LIB)

    logger.info("Applying Plex labels to %d items...", len(tagged))
    for item in tagged:
        lib_name, libtype = _lib_and_type(item.media_type)
        results = plex.search(lib_name, item.title, libtype)
        if results:
            plex.add_labels(results[0], item.labels)
        else:
            logger.warning("Plex item not found after scan: %s", item.title)

    logger.info("Ingestion complete.")


def _genre_labels(genre_ids: list[int], config: Settings) -> list[str]:
    return [config.DISCOVER_GENRES[str(gid)] for gid in genre_ids if str(gid) in config.DISCOVER_GENRES]


def _lib_and_type(media_type: str) -> tuple[str, str]:
    if media_type in ("movie", "movies"):
        return _DISCOVER_MOVIES_LIB, "movie"
    return _DISCOVER_SHOWS_LIB, "show"


def run(config: Settings | None = None) -> None:
    config = config or Settings()

    sched = Schedule(_INGEST_SCHEDULE_PATH)
    if not sched.is_enabled():
        logger.info("Ingestion schedule is disabled — exiting.")
        return

    items, themed_lists = fetch_media(config)
    filtered = filter_media(items, config)
    write_dummies(filtered, config)
    kometa_config.generate(themed_lists)
