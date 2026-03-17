import logging
import os
import sqlite3
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS simkl_list_items (
    simkl_id   INTEGER PRIMARY KEY,
    tmdb_id    INTEGER,
    title      TEXT NOT NULL,
    media_type TEXT NOT NULL,
    list_name  TEXT,
    list_order INTEGER,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
"""


class SimklListDB:
    def __init__(self, db_path: Path | str) -> None:
        self._db_path = str(db_path)
        self._lock = threading.Lock()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        os.makedirs(os.path.dirname(self._db_path) or ".", exist_ok=True)
        with self._lock:
            with self._connect() as conn:
                conn.execute(_SCHEMA)

    def get_all_for_list(self, list_name: str) -> list[sqlite3.Row]:
        """Return all items for a list, ordered by list_order."""
        with self._connect() as conn:
            return conn.execute(
                "SELECT * FROM simkl_list_items WHERE list_name = ? ORDER BY list_order",
                (list_name,),
            ).fetchall()

    def get_by_simkl_ids(self, simkl_ids: list[int]) -> dict[int, sqlite3.Row]:
        """Bulk lookup rows by simkl_id. Returns {simkl_id: row}."""
        if not simkl_ids:
            return {}
        placeholders = ",".join("?" * len(simkl_ids))
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM simkl_list_items WHERE simkl_id IN ({placeholders})",
                simkl_ids,
            ).fetchall()
        return {row["simkl_id"]: row for row in rows}

    def upsert_items(self, items: list[dict]) -> None:
        """INSERT OR REPLACE a batch of items.

        Each dict must have: simkl_id, title, media_type.
        Optional: tmdb_id, list_name, list_order.
        """
        with self._lock:
            with self._connect() as conn:
                conn.executemany(
                    """
                    INSERT INTO simkl_list_items
                        (simkl_id, tmdb_id, title, media_type, list_name, list_order, updated_at)
                    VALUES
                        (:simkl_id, :tmdb_id, :title, :media_type, :list_name, :list_order,
                         datetime('now'))
                    ON CONFLICT(simkl_id) DO UPDATE SET
                        tmdb_id    = excluded.tmdb_id,
                        title      = excluded.title,
                        media_type = excluded.media_type,
                        list_name  = excluded.list_name,
                        list_order = excluded.list_order,
                        updated_at = excluded.updated_at
                    """,
                    items,
                )

    def remove_from_list(self, simkl_ids: list[int]) -> None:
        """Set list_name and list_order to NULL for the given simkl_ids (soft remove)."""
        if not simkl_ids:
            return
        placeholders = ",".join("?" * len(simkl_ids))
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    f"UPDATE simkl_list_items SET list_name = NULL, list_order = NULL, "
                    f"updated_at = datetime('now') WHERE simkl_id IN ({placeholders})",
                    simkl_ids,
                )
        logger.info("Removed %d items from their lists.", len(simkl_ids))

    def query_by_list(self, list_name: str) -> list[sqlite3.Row]:
        """Return items for a list ordered by list_order (for /arr/list)."""
        return self.get_all_for_list(list_name)
