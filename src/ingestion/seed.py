import dataclasses
import json
import logging
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from itertools import chain
from pathlib import Path
from zoneinfo import ZoneInfo

from src.clients.plex_client import PlexClient
from src.clients.simkl_client.simkl_client import SimklClient, SimklRateLimitError
from src.clients.simkl_client.simkl_models import SimklItem, SimklShow, TrendingSize, TrendingTimeframe
from src.clients.tmdb_client import TmdbClient
from src.config import Settings
from src.ingestion.shared import (
    MediaItem,
    _dedup_by_tmdb_id,
    fetch_curated_lists,
    filter_media,
    label_discover_items,
    write_dummies,
)
from src.jobs.state import CallState

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Simkl ID → TMDB ID lookup cache
# ---------------------------------------------------------------------------


def _load_id_cache(path: Path) -> dict[int, int]:
    try:
        raw = json.loads(path.read_text())
        return {int(k): v for k, v in raw.items()}
    except FileNotFoundError:
        return {}


def _save_id_cache(cache: dict[int, int], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, indent=2))


def _resolve_tmdb_ids(items: list[SimklItem], config: Settings) -> None:
    """Enrich items in-place with TMDB IDs.

    Resolution order:
    1. Already set — skip.
    2. Lookup table (disk cache) — no API call.
    3. Simkl /search/id endpoint.
    4. TMDB title search fallback.
    Updates the lookup table for any newly resolved IDs.
    """
    cache = _load_id_cache(config.SIMKL_ID_CACHE_FILE)
    simkl = SimklClient(config=config)
    tmdb_client = TmdbClient(config=config)
    dirty = False
    simkl_exhausted = False

    for item in items:
        if item.ids.tmdb is not None:
            continue
        simkl_id = item.ids.simkl
        if simkl_id is None:
            continue

        if simkl_id in cache:
            item.ids.tmdb = cache[simkl_id]
            continue

        if not simkl_exhausted:
            try:
                ids = simkl.lookup_ids_by_simkl_id(simkl_id)
                if ids and ids.tmdb is not None:
                    item.ids.tmdb = ids.tmdb
                    cache[simkl_id] = ids.tmdb
                    dirty = True
                    continue
            except SimklRateLimitError:
                logger.warning("All Simkl API keys rate limited — switching to TMDB title search for remaining items")
                simkl_exhausted = True

        tmdb_id = tmdb_client.search_tv_by_title(item.title, item.year)
        if tmdb_id is not None:
            item.ids.tmdb = tmdb_id
            cache[simkl_id] = tmdb_id
            dirty = True
            logger.debug("Resolved '%s' via TMDB title search → tmdb=%d", item.title, tmdb_id)

    # if dirty:
    #     _save_id_cache(cache, config.SIMKL_ID_CACHE_FILE)
    #     logger.info("Saved %d entries to Simkl ID cache.", len(cache))


@dataclass
class SeedData:
    curated: dict[str, Sequence[SimklItem]] = field(default_factory=dict)
    discover: list[MediaItem] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------


def _save_seed_cache(data: SeedData, path: Path, tz: ZoneInfo) -> None:
    payload = {
        "saved_at": datetime.now(tz).isoformat(),
        "curated": {k: [item.model_dump() for item in v] for k, v in data.curated.items()},
        "discover": [dataclasses.asdict(item) for item in data.discover],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))
    logger.info("Seed data cached to %s.", path)


def _load_seed_cache(path: Path, ttl_hours: int, tz: ZoneInfo) -> SeedData | None:
    try:
        raw = json.loads(path.read_text())
    except FileNotFoundError:
        logger.info("No seed cache found at %s.", path)
        return None
    saved_at = datetime.fromisoformat(raw["saved_at"])
    age_hours = (datetime.now(tz) - saved_at).total_seconds() / 3600
    if age_hours > ttl_hours:
        logger.info("Seed cache expired (%.1fh old, TTL=%dh).", age_hours, ttl_hours)
        return None
    logger.info("Using cached seed data (%.1fh old).", age_hours)
    curated: dict[str, Sequence[SimklItem]] = {
        k: [SimklShow.model_validate(d) for d in v] for k, v in raw["curated"].items()
    }
    discover = [MediaItem(**d) for d in raw["discover"]]
    return SeedData(curated=curated, discover=discover)


# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------


def fetch_raw_seed_media(
    config: Settings,
    curated_max: int = 100,
    discover_timeframe: TrendingTimeframe = TrendingTimeframe.WEEK,
    discover_size: TrendingSize = TrendingSize.TOP_500,
) -> SeedData:
    simkl = SimklClient(config=config)
    tmdb = TmdbClient(config=config)

    # Curated collections — written directly as Plex collections
    curated = fetch_curated_lists(simkl, config, curated_max)

    all_curated = [item for items in curated.values() for item in items]
    _resolve_tmdb_ids(all_curated, config)

    # Discover candidates — filtered and written as dummies; Kometa creates collections
    # Curated items are included so their dummy files exist when collections are built.
    discover: list[MediaItem] = []
    for items in curated.values():
        for item in items:
            if item.ids.tmdb is not None:
                discover.append(
                    MediaItem(
                        title=item.title,
                        year=str(item.year) if item.year else None,
                        media_type="tv",
                        tmdb_id=item.ids.tmdb,
                    )
                )

    for item in simkl.fetch_trending_movies(timeframe=discover_timeframe, size=discover_size):
        if item.ids.tmdb is None:
            continue
        discover.append(
            MediaItem(
                title=item.title,
                year=str(item.year) if item.year else None,
                media_type="movie",
                tmdb_id=item.ids.tmdb,
            )
        )

    for item in simkl.fetch_trending_tv(timeframe=discover_timeframe, size=discover_size):
        if item.ids.tmdb is None:
            continue
        discover.append(
            MediaItem(
                title=item.title,
                year=str(item.year) if item.year else None,
                media_type="tv",
                tmdb_id=item.ids.tmdb,
            )
        )

    for item in chain(tmdb.get_trending_movies(), tmdb.get_popular_movies(), tmdb.get_popular_korean_movies()):
        discover.append(
            MediaItem(
                title=item.title,
                year=item.year,
                media_type=item.media_type,
                tmdb_id=item.tmdb_id,
                original_language=item.original_language,
                vote_average=item.vote_average,
                vote_count=item.vote_count,
            )
        )

    for item in chain(tmdb.get_trending_shows(), tmdb.get_popular_shows(), tmdb.get_popular_korean_shows()):
        discover.append(
            MediaItem(
                title=item.title,
                year=item.year,
                media_type=item.media_type,
                tmdb_id=item.tmdb_id,
                original_language=item.original_language,
                vote_average=item.vote_average,
                vote_count=item.vote_count,
            )
        )

    deduped = _dedup_by_tmdb_id(discover)
    logger.info("Fetched %d discover candidates (%d after dedup).", len(discover), len(deduped))
    return SeedData(curated=curated, discover=deduped)


def create_curated_collections(
    config: Settings,
    curated: dict[str, Sequence[SimklItem]],
) -> None:
    """Upsert ordered Plex collections for each curated Simkl list.

    Existing collections are deleted and recreated so the trending rank order
    is always fresh. Each item is searched across all show libraries (Discover
    and real) so the collection works whether an item is a dummy placeholder or
    already owned content.
    """
    plex = PlexClient(config)
    all_sections = [config.DISCOVER_SHOWS_LIB, config.DISCOVER_MOVIES_LIB, *config.REAL_LIBS]

    for collection_name, items in curated.items():
        item_list = list(items)
        logger.info("Building curated collection '%s' from %d Simkl items.", collection_name, len(item_list))

        found: list[tuple] = []  # (plex_item, section_name)
        for item in item_list:
            if item.ids.tmdb is None:
                logger.info("  '%s' → skipped (no TMDB ID) ids=%s", item.title, item.ids.model_dump(exclude_none=True))
                continue
            for section_name in all_sections:
                try:
                    results = plex.search(section_name, item.title, "show")
                    if results:
                        matched = results[0]
                        logger.info(
                            "  '%s' (tmdb=%s) → matched '%s' in '%s' (ratingKey=%s)",
                            item.title,
                            item.ids.tmdb,
                            matched.title,
                            section_name,
                            matched.ratingKey,
                        )
                        found.append((matched, section_name))
                        break
                except Exception:
                    continue
            else:
                logger.info("  '%s' (tmdb=%s) → not found in any library", item.title, item.ids.tmdb)

        if not found:
            logger.warning("No Plex items found for curated collection '%s' — skipping.", collection_name)
            continue

        # All items must be in the same section for a Plex collection.
        # Use the section with the most matches (prefer DISCOVER_SHOWS_LIB on tie).
        section_counts = Counter(section for _, section in found)
        target_section = max(
            section_counts,
            key=lambda s: (section_counts[s], s == config.DISCOVER_SHOWS_LIB),
        )
        rating_keys = [plex_item.ratingKey for plex_item, section in found if section == target_section]

        logger.info(
            "Creating collection '%s' in '%s' with %d/%d items.",
            collection_name,
            target_section,
            len(rating_keys),
            len(item_list),
        )
        plex.delete_collection_if_exists(target_section, collection_name)
        plex.create_custom_ordered_collection(collection_name, rating_keys)
        logger.info("Upserted curated collection '%s'.", collection_name)


def run(config: Settings | None = None, *, test_run: bool = False, use_cache: bool = False) -> None:
    config = config or Settings()

    try:
        tz = ZoneInfo(config.TIMEZONE)
        logger.info("run: use_cache=%s test_run=%s cache_file=%s", use_cache, test_run, config.SEED_CACHE_FILE)
        if use_cache and (cached := _load_seed_cache(config.SEED_CACHE_FILE, config.SEED_CACHE_TTL_HOURS, tz)):
            data = cached
        else:
            logger.info("Cache miss or use_cache=False — fetching live data.")
            if test_run:
                logger.info("Test run — using reduced fetch sizes.")
                data = fetch_raw_seed_media(
                    config,
                    discover_timeframe=TrendingTimeframe.MONTH,
                    discover_size=TrendingSize.TOP_100,
                )
            else:
                data = fetch_raw_seed_media(config)
            # only save a new seed cache when getting new data, otherwise
            # the recorded fetch date is updated even on cache hit
            _save_seed_cache(data, config.SEED_CACHE_FILE, tz)

        filtered = filter_media(data.discover, config)

        write_dummies(filtered, config)

        plex = PlexClient(config)
        logger.info("Triggering Plex library scans...")
        plex.refresh_and_wait(config.DISCOVER_MOVIES_LIB, config.DISCOVER_SHOWS_LIB)

        label_discover_items(filtered, plex, config)

        logger.info("Creating curated Plex collections...")
        create_curated_collections(config, data.curated)

        CallState(config.STATE_FILE).record("seed")
        logger.info("Seed complete.")
    except Exception:
        logger.exception("Seed failed.")
