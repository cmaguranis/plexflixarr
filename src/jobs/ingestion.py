import logging
import re
from dataclasses import dataclass, field

from src.clients.anilist_client import AniListClient
from src.clients.mdblist_client import MdblistClient, MdblistUnavailableError
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
    tmdb_id: int | None = None  # None for Trakt items; MDBList quality check is skipped
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
    plex = PlexClient(config)

    # --- Batch MDBList quality gate ---
    # Group TMDB items by media_type for bulk API calls (2 calls total: movie + show).
    # Trakt/AniList items have no tmdb_id and skip the quality gate entirely.
    quality_pass: dict[int, bool] = {}
    mdblist_available = bool(config.MDBLIST_API_KEY)

    if mdblist_available:
        mdblist = MdblistClient(config)
        try:
            for m_type in ("movie", "show"):
                # MDBList uses "show"; TMDB uses "tv" — normalise here
                ids = [
                    i.tmdb_id
                    for i in items
                    if i.tmdb_id is not None
                    and (i.media_type == m_type or (m_type == "show" and i.media_type == "tv"))
                ]
                if ids:
                    quality_pass.update(mdblist.batch_quality_check(ids, m_type))
        except MdblistUnavailableError as exc:
            logger.warning(
                "MDBList unavailable (%s) — falling back to TMDB vote_average >= %.1f"
                " with >= %d votes",
                exc, config.TMDB_MIN_VOTE_AVERAGE, config.TMDB_MIN_VOTE_COUNT,
            )
            mdblist_available = False

    # --- Per-item filtering ---
    filtered: list[MediaItem] = []
    for item in items:
        if item.tmdb_id is not None:
            if mdblist_available:
                if not quality_pass.get(item.tmdb_id, False):
                    logger.debug("Rejected (quality): %s", item.title)
                    continue
            else:
                if (
                    item.vote_count < config.TMDB_MIN_VOTE_COUNT
                    or item.vote_average < config.TMDB_MIN_VOTE_AVERAGE
                ):
                    logger.debug(
                        "Rejected (TMDB fallback quality, %.1f/%d votes): %s",
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

    logger.info("Applying Plex labels to %d items...", len(tagged))
    for item in tagged:
        lib_name, libtype = _lib_and_type(item.media_type)
        results = plex.search(lib_name, sanitize_filename(_base_title(item.title)), libtype)
        if results:
            plex.add_labels(results[0], item.labels)
        else:
            logger.warning("Plex item not found after scan: %s", item.title)

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
