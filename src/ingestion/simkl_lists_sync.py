import logging
from collections.abc import Sequence

from src.clients.simkl_client.simkl_client import SimklClient, SimklRateLimitError
from src.clients.simkl_client.simkl_models import SimklItem, TrendingSize, TrendingTimeframe
from src.clients.tmdb_client import TmdbClient
from src.clients.tvdb_client import TvdbClient
from src.config import Settings
from src.db.simkl_lists import SimklListDB
from src.ingestion.shared import (
    fetch_curated_lists,
)

logger = logging.getLogger(__name__)


def _resolve_ids(items: list[SimklItem], config: Settings) -> None:
    """Enrich items in-place with TMDB and TVDB IDs.

    Resolution order (per ID type):
    1. Already set — skip.
    2. Simkl /search/id endpoint — returns both tmdb and tvdb.
    3. TMDB title search fallback (for missing tmdb_id).
    4. TVDB title search fallback (for missing tvdb_id).
    """
    simkl = SimklClient(config=config)
    tmdb_client = TmdbClient(config=config)
    tvdb_client = TvdbClient(config=config)
    simkl_exhausted = False

    for item in items:
        simkl_id = item.ids.simkl
        if simkl_id is None:
            continue
        if item.ids.tmdb is not None and item.ids.tvdb is not None:
            continue

        if not simkl_exhausted:
            try:
                ids = simkl.lookup_ids_by_simkl_id(simkl_id)
                if ids:
                    if item.ids.tmdb is None and ids.tmdb is not None:
                        item.ids.tmdb = ids.tmdb
                    if item.ids.tvdb is None and ids.tvdb is not None:
                        item.ids.tvdb = ids.tvdb
            except SimklRateLimitError:
                logger.warning("All Simkl API keys rate limited — switching to title search for remaining items")
                simkl_exhausted = True

        if item.ids.tmdb is None:
            tmdb_id = tmdb_client.search_tv_by_title(item.title, item.year)
            if tmdb_id is not None:
                item.ids.tmdb = tmdb_id
                logger.debug("Resolved '%s' via TMDB title search → tmdb=%d", item.title, tmdb_id)

        if item.ids.tvdb is None:
            tvdb_id = tvdb_client.search_tv_by_title(item.title, item.year)
            if tvdb_id is not None:
                item.ids.tvdb = tvdb_id
                logger.debug("Resolved '%s' via TVDB title search → tvdb=%d", item.title, tvdb_id)


def sync_list_to_db(list_name: str, items: Sequence[SimklItem], db: SimklListDB, media_type: str = "tv") -> None:
    """Diff Simkl items against DB for this list_name.

    - Upserts all current items with updated order and list_name.
    - Removes membership for items previously in this list that are no longer present.
    """
    simkl_ids = [item.ids.simkl for item in items if item.ids.simkl is not None]

    existing = db.get_all_for_list(list_name)
    existing_ids = {row["simkl_id"] for row in existing}
    current_ids = set(simkl_ids)

    removed_ids = list(existing_ids - current_ids)
    if removed_ids:
        logger.info("Removing %d items from '%s' in DB.", len(removed_ids), list_name)
        db.remove_from_list(removed_ids, list_name)

    rows = [
        {
            "simkl_id": item.ids.simkl,
            "tmdb_id": item.ids.tmdb,
            "tvdb_id": item.ids.tvdb,
            "title": item.title,
            "media_type": media_type,
            "list_name": list_name,
            "list_order": order,
        }
        for order, item in enumerate(items)
        if item.ids.simkl is not None
    ]
    db.upsert_items(rows)
    logger.info("Upserted %d items for '%s'.", len(rows), list_name)


def run(config: Settings | None = None, curated_max: int = 100) -> None:
    config = config or Settings()
    try:
        db = SimklListDB(config.SIMKL_LISTS_DB_FILE)
        db.init_db()

        simkl = SimklClient(config=config)

        # --- Trending lists first (IDs already embedded in CDN JSON) ---
        # trending_tv = simkl.fetch_trending_tv(TrendingTimeframe.WEEK, TrendingSize.TOP_100)
        # trending_movies = simkl.fetch_trending_movies(TrendingTimeframe.WEEK, TrendingSize.TOP_100)
        # trending_anime = simkl.fetch_trending_anime(TrendingTimeframe.WEEK, TrendingSize.TOP_100)

        # sync_list_to_db(config.SIMKL_LIST_NAME_TRENDING_TV, trending_tv, db, media_type="tv")
        # sync_list_to_db(config.SIMKL_LIST_NAME_TRENDING_MOVIES, trending_movies, db, media_type="movie")
        # sync_list_to_db(config.SIMKL_LIST_NAME_TRENDING_ANIME, trending_anime, db, media_type="tv")

        # --- Curated lists ---
        curated = fetch_curated_lists(simkl, config, curated_max)
        all_items = [item for items in curated.values() for item in items]

        # Pre-fill IDs from DB rows seeded by trending sync above
        db_rows = db.get_by_simkl_ids([i.ids.simkl for i in all_items if i.ids.simkl])
        for item in all_items:
            if item.ids.simkl in db_rows:
                row = db_rows[item.ids.simkl]
                item.ids.tmdb = item.ids.tmdb or row["tmdb_id"]
                item.ids.tvdb = item.ids.tvdb or row["tvdb_id"]

        _resolve_ids(all_items, config)

        for list_name, items in curated.items():
            sync_list_to_db(list_name, list(items), db)

        logger.info("Simkl lists sync complete.")
    except Exception:
        logger.exception("Simkl lists sync failed.")
