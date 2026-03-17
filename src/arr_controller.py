from fastapi import APIRouter

from src.config import Settings
from src.db.simkl_lists import SimklListDB

router = APIRouter(prefix="/arr")


@router.get("/list")
def get_list(name: str) -> list[dict]:
    """Return items for a named Simkl list, ordered by their Simkl rank."""
    config = Settings()
    db = SimklListDB(config.SIMKL_LISTS_DB_FILE)
    db.init_db()
    rows = db.query_by_list(name)
    return [
        {
            "title": row["title"],
            "tmdb_id": row["tmdb_id"],
            "media_type": row["media_type"],
            "list_order": row["list_order"],
        }
        for row in rows
    ]
