import logging
import re
import time
from dataclasses import dataclass, field

from src.clients.anilist_client import AniListClient
from src.clients.plex_client import PlexClient
from src.clients.tmdb_client import TmdbClient
from src.clients.trakt_client import TraktClient, TraktList
from src.config import Settings
from src.dummy import create_dummy, ensure_template, sanitize_filename
from src.jobs import kometa_config
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
    genre_ids: list[int] = field(default_factory=list)
    vote_average: float = 0.0
    vote_count: int = 0


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
            vote_average=item.vote_average, vote_count=item.vote_count,
        ))

    logger.info("Fetching TMDB trending content...")
    for item in tmdb.fetch_trending(config.PAGES_PER_PROVIDER):
        items.append(MediaItem(
            title=item.title, year=item.year, media_type=item.media_type, tmdb_id=item.tmdb_id,
            genre_ids=item.genre_ids,
            labels=item.labels + _genre_labels(item.genre_ids, config),
            vote_average=item.vote_average, vote_count=item.vote_count,
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
            anilist_id=item.anilist_id,
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
                anilist_id=item.anilist_id,
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
    plex = PlexClient(config)
    filtered: list[MediaItem] = []

    for item in items:
        # TMDB items carry vote data; Trakt/AniList items are personalised, skip quality gate
        if item.tmdb_id is not None:
            if (
                item.vote_count < config.TMDB_MIN_VOTE_COUNT
                or item.vote_average < config.TMDB_MIN_VOTE_AVERAGE
            ):
                logger.debug(
                    "Rejected (quality, %.1f/%d votes): %s",
                    item.vote_average, item.vote_count, item.title,
                )
                continue

        real_libs = (
            config.REAL_MOVIES_LIBS
            if item.media_type in ("movie", "movies")
            else config.REAL_SHOWS_LIBS
        )
        if plex.exists_in_any(real_libs, _base_title(item.title), item.media_type):
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

    by_id: list[MediaItem] = []
    by_title: list[MediaItem] = []
    for item in tagged:
        if item.tmdb_id is not None or item.anilist_id is not None:
            by_id.append(item)
        else:
            by_title.append(item)

    logger.info("Applying Plex labels to %d items (%d by ID, %d by title)...", len(tagged), len(by_id), len(by_title))

    def _label(item: MediaItem, results: list) -> None:
        if results:
            plex.add_labels(results[0], item.labels)
        else:
            logger.warning("Plex item not found after scan: %s", item.title)

    for item in by_id:
        lib_name, libtype = _lib_and_type(item.media_type)
        results = None
        for attempt in range(1, 4):
            if item.tmdb_id is not None:
                results = plex.find_by_tmdb_id(lib_name, item.tmdb_id, libtype)
            else:
                results = plex.find_by_anilist_id(lib_name, item.anilist_id, libtype)
            if results:
                break
            logger.debug("Plex item not yet indexed (attempt %d/3): %s", attempt, item.title)
            time.sleep(10)
        _label(item, results)

    if by_title:
        logger.info("Looking up %d title-only items by name...", len(by_title))
        for item in by_title:
            lib_name, libtype = _lib_and_type(item.media_type)
            results = plex.search(lib_name, sanitize_filename(_base_title(item.title)), libtype)
            _label(item, results)

    logger.info("Ingestion complete.")


_SEASON_SUFFIX_RE = re.compile(
    r"\s+(?:Season|Part|Cour)\s+\d+.*$"   # "Season 3: ...", "Part 2", "Cour 2"
    r"|\s+\(\d{4}\)\s*$",                  # trailing "(2011)"
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

    items, themed_lists = fetch_media(config)
    filtered = filter_media(items, config)
    write_dummies(filtered, config)
    kometa_config.generate(themed_lists, output_dir=config.KOMETA_CONFIG_PATH)
