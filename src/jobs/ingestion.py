import logging
import re
from dataclasses import dataclass, field

from src.clients.anilist_client import AniListClient
from src.clients.anime_list_client import resolve_tmdb_id
from src.clients.plex_client import PlexClient
from src.clients.tmdb_client import TmdbClient
from src.clients.trakt_client import TraktClient
from src.config import Settings
from src.dummy import create_dummy, ensure_template
from src.jobs import discovery_order
from src.jobs.schedule import Schedule

logger = logging.getLogger(__name__)

_INGEST_SCHEDULE_PATH = "scripts/ingest_schedule.json"
_DISCOVER_MOVIES_LIB = "Discover Movies"
_DISCOVER_SHOWS_LIB = "Discover Shows"


@dataclass
class MediaItem:
    title: str
    year: str | None
    media_type: str
    labels: list[str] = field(default_factory=list)
    tmdb_id: int | None = None
    anilist_id: int | None = None
    original_language: str = ""
    genre_ids: list[int] = field(default_factory=list)
    vote_average: float = 0.0
    vote_count: int = 0


def fetch_media(config: Settings) -> list[MediaItem]:
    """Step 1: Fetch raw candidates from TMDB, Trakt, and AniList."""
    items: list[MediaItem] = []

    tmdb = TmdbClient(config)

    logger.info("Fetching TMDB streaming content...")
    for item in tmdb.fetch_streaming(config.PAGES_PER_PROVIDER):
        items.append(
            MediaItem(
                title=item.title,
                year=item.year,
                media_type=item.media_type,
                tmdb_id=item.tmdb_id,
                original_language=item.original_language,
                genre_ids=item.genre_ids,
                labels=item.labels + _genre_labels(item.genre_ids, config),
                vote_average=item.vote_average,
                vote_count=item.vote_count,
            )
        )

    logger.info("Fetching TMDB trending content...")
    for item in tmdb.fetch_trending(config.PAGES_PER_PROVIDER):
        items.append(
            MediaItem(
                title=item.title,
                year=item.year,
                media_type=item.media_type,
                tmdb_id=item.tmdb_id,
                original_language=item.original_language,
                genre_ids=item.genre_ids,
                labels=item.labels + _genre_labels(item.genre_ids, config),
                vote_average=item.vote_average,
                vote_count=item.vote_count,
            )
        )

    trakt = TraktClient(config)

    logger.info("Fetching Trakt recommendations...")
    for item in trakt.fetch_recommendations():
        items.append(
            MediaItem(
                title=item.title,
                year=item.year,
                media_type=item.media_type,
                labels=["Discover_Recs"],
                tmdb_id=item.tmdb_id,
            )
        )

    if config.TRAKT_USERNAME:
        logger.info("Fetching Couchmoney themed lists for %s...", config.TRAKT_USERNAME)
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

    anilist = AniListClient(config)

    logger.info("Fetching AniList trending anime...")
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

    # Fetch AniList personalised anime recommendations (requires ANILIST_USERNAME)
    if config.ANILIST_USERNAME:
        logger.info("Fetching AniList recommendations for %s...", config.ANILIST_USERNAME)
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

    # Resolve AniList IDs to TMDb IDs so folders get {tmdb-N} names and dedup works across sources
    for item in items:
        if item.anilist_id is not None and item.tmdb_id is None:
            item.tmdb_id = resolve_tmdb_id(item.anilist_id)

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
    return deduped


def filter_media(items: list[MediaItem], config: Settings) -> list[MediaItem]:
    """Step 2: Remove low-quality titles and those already owned in real Plex libraries."""
    plex = PlexClient(config)
    filtered: list[MediaItem] = []

    for item in items:
        if item.original_language and item.original_language in config.EXCLUDED_LANGUAGES:
            logger.debug("Rejected (language=%s): %s", item.original_language, item.title)
            continue

        # TMDB items carry vote data; Trakt/AniList items are personalised, skip quality gate
        if item.vote_count > 0 and (
            item.vote_count < config.TMDB_MIN_VOTE_COUNT or item.vote_average < config.TMDB_MIN_VOTE_AVERAGE
        ):
            logger.debug(
                "Rejected (quality, %.1f/%d votes): %s",
                item.vote_average,
                item.vote_count,
                item.title,
            )
            continue

        real_libs = config.REAL_MOVIES_LIBS if item.media_type in ("movie", "movies") else config.REAL_SHOWS_LIBS
        if plex.exists_in_any(real_libs, _base_title(item.title), item.media_type):
            logger.debug("Already in real library, skipping: %s", item.title)
            continue

        filtered.append(item)

    logger.info("%d items passed filters.", len(filtered))
    return filtered


def apply_labels(items: list[MediaItem], plex: PlexClient) -> None:
    """
    Find each item in the Discover library by title and apply its labels.

    Folder naming already embeds the TMDB ID (``Title (Year) {tmdb-N}``), so Plex
    resolves matches correctly at scan time. Plex's new metadata agent sets the
    primary ``guid`` to ``plex://...``, not ``tmdb://...``, so guid-based search
    does not work — title search is used for all items instead.

    Only labels not already present on the item are added.
    """
    logger.info("Applying Plex labels to %d items...", len(items))

    def _label(item: MediaItem) -> None:
        lib_name, libtype = _lib_and_type(item.media_type)
        results = plex.query_search(lib_name, _base_title(item.title), libtype)
        if not results:
            logger.warning("Plex item not found: %s", item.title)
            return
        plex_item = results[0]
        existing = {lbl.tag for lbl in plex_item.labels}
        missing = [lbl for lbl in item.labels if lbl not in existing]
        if missing:
            plex.add_labels(plex_item, missing)

    for item in items:
        _label(item)


def write_dummies(items: list[MediaItem], config: Settings) -> None:
    """Step 3: Create dummy .mkv files, trigger Plex scan, and apply labels."""
    ensure_template(config.TEMPLATE_FILE)
    tagged = [
        item for item in items if create_dummy(item.title, item.year, item.media_type, config, tmdb_id=item.tmdb_id)
    ]

    if not tagged:
        logger.info("No new dummy files created.")
        return

    plex = PlexClient(config)
    logger.info("Triggering Plex library scans...")
    plex.refresh_and_wait(_DISCOVER_MOVIES_LIB, _DISCOVER_SHOWS_LIB)
    apply_labels(tagged, plex)
    logger.info("Ingestion complete.")


_SEASON_SUFFIX_RE = re.compile(
    r"\s+(?:Season|Part|Cour)\s+\d+.*$"  # "Season 3: ...", "Part 2", "Cour 2"
    r"|\s+\(\d{4}\)\s*$",  # trailing "(2011)"
    re.IGNORECASE,
)


def _base_title(title: str) -> str:
    """Strip trailing season/part/year suffixes for Plex dedup lookups."""
    return _SEASON_SUFFIX_RE.sub("", title).strip()


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

    items = fetch_media(config)
    filtered = filter_media(items, config)
    write_dummies(filtered, config)
    discovery_order.run(config)
