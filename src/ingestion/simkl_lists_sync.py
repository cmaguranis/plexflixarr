import logging

from src.clients.mdblist_client import MdblistClient
from src.clients.simkl_client.simkl_client import SimklClient
from src.clients.simkl_client.simkl_models import SimklItem, SimklMovie
from src.config import Settings
from src.db.simkl_lists import SimklListDB
from src.ingestion.seed import _resolve_tmdb_ids
from src.ingestion.shared import fetch_curated_lists
from src.jobs.state import CallState

logger = logging.getLogger(__name__)


def sync_list_to_db(list_name: str, items: list[SimklItem], db: SimklListDB) -> None:
    """Diff Simkl items against DB for this list_name.

    - Upserts all current items with updated order and list_name.
    - Sets list_name=NULL for items previously in this list that are no longer present.
    """
    simkl_ids = [item.ids.simkl for item in items if item.ids.simkl is not None]

    existing = db.get_all_for_list(list_name)
    existing_ids = {row["simkl_id"] for row in existing}
    current_ids = set(simkl_ids)

    removed_ids = list(existing_ids - current_ids)
    if removed_ids:
        logger.info("Removing %d items from '%s' in DB.", len(removed_ids), list_name)
        db.remove_from_list(removed_ids)

    rows = [
        {
            "simkl_id": item.ids.simkl,
            "tmdb_id": item.ids.tmdb,
            "title": item.title,
            "media_type": "tv",
            "list_name": list_name,
            "list_order": order,
        }
        for order, item in enumerate(items)
        if item.ids.simkl is not None
    ]
    db.upsert_items(rows)
    logger.info("Upserted %d items for '%s'.", len(rows), list_name)


def regenerate_mdblist(list_name: str, items: list[SimklItem], mdblist: MdblistClient) -> None:
    """Delete the existing MDBList list by name (if found), create a new one with the
    same name, and populate it with the current items.
    """
    existing = mdblist.find_list_by_name(list_name)
    if existing:
        mdblist.delete_list(existing["id"])

    new_id = mdblist.create_list(list_name)

    movies = [{"tmdb": item.ids.tmdb} for item in items
              if item.ids.tmdb is not None and isinstance(item, SimklMovie)]
    shows = [{"tmdb": item.ids.tmdb} for item in items
             if item.ids.tmdb is not None and not isinstance(item, SimklMovie)]
    show_items = [item for item in items if item.ids.tmdb is not None and not isinstance(item, SimklMovie)]
    for i, item in enumerate(show_items[:10]):
        logger.info("  [%d] %s (tmdb=%s)", i + 1, item.title, item.ids.tmdb)
    if movies or shows:
        mdblist.add_items_to_list(new_id, movies=movies, shows=shows)
    logger.info("Regenerated MDBList '%s' (id=%d) with %d movies, %d shows.", list_name, new_id, len(movies), len(shows))


def run(config: Settings | None = None, curated_max: int = 100) -> None:
    config = config or Settings()
    try:
        db = SimklListDB(config.SIMKL_LISTS_DB_FILE)
        db.init_db()

        simkl = SimklClient(config=config)
        curated = fetch_curated_lists(simkl, config, curated_max)

        # Resolve TMDB IDs — skips items already in DB with a tmdb_id
        all_items = [item for items in curated.values() for item in items]
        _resolve_tmdb_ids(all_items, config)

        mdblist = MdblistClient(config)

        for list_name, items in curated.items():
            item_list = list(items)
            sync_list_to_db(list_name, item_list, db)
            regenerate_mdblist(list_name, item_list, mdblist)

        CallState(config.STATE_FILE).record("simkl_lists_sync")
        logger.info("Simkl lists sync complete.")
    except Exception:
        logger.exception("Simkl lists sync failed.")
