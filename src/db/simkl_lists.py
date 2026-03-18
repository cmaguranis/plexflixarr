import logging
import os
import sqlite3
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

_SCHEMA_ITEMS = """
CREATE TABLE IF NOT EXISTS simkl_list_items (
    simkl_id   INTEGER PRIMARY KEY,
    tmdb_id    INTEGER,
    tvdb_id    INTEGER,
    title      TEXT NOT NULL,
    media_type TEXT NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
"""

_SCHEMA_MEMBERSHIPS = """
CREATE TABLE IF NOT EXISTS simkl_list_memberships (
    simkl_id   INTEGER NOT NULL,
    list_name  TEXT NOT NULL,
    list_order INTEGER,
    PRIMARY KEY (simkl_id, list_name),
    FOREIGN KEY (simkl_id) REFERENCES simkl_list_items(simkl_id)
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
                conn.execute(_SCHEMA_ITEMS)
                conn.execute(_SCHEMA_MEMBERSHIPS)
                # Add tvdb_id column to existing DBs that predate this schema
                try:
                    conn.execute("ALTER TABLE simkl_list_items ADD COLUMN tvdb_id INTEGER")
                except sqlite3.OperationalError as e:
                    if "duplicate column name" not in str(e):
                        raise
                # Migrate old list_name/list_order columns into memberships table
                try:
                    conn.execute("""
                        INSERT OR IGNORE INTO simkl_list_memberships (simkl_id, list_name, list_order)
                        SELECT simkl_id, list_name, list_order
                        FROM simkl_list_items
                        WHERE list_name IS NOT NULL
                    """)
                except sqlite3.OperationalError as e:
                    if "no such column" not in str(e):
                        raise

    def get_all_for_list(self, list_name: str) -> list[sqlite3.Row]:
        """Return all items for a list, ordered by list_order."""
        with self._connect() as conn:
            return conn.execute(
                """
                SELECT i.simkl_id, i.tmdb_id, i.tvdb_id, i.title, i.media_type,
                       m.list_name, m.list_order, i.updated_at
                FROM simkl_list_items i
                JOIN simkl_list_memberships m ON i.simkl_id = m.simkl_id
                WHERE m.list_name = ?
                ORDER BY m.list_order
                """,
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
        """Upsert item data and list memberships.

        Each dict must have: simkl_id, title, media_type.
        Optional: tmdb_id, tvdb_id, list_name, list_order.
        """
        with self._lock:
            with self._connect() as conn:
                conn.executemany(
                    """
                    INSERT INTO simkl_list_items
                        (simkl_id, tmdb_id, tvdb_id, title, media_type, updated_at)
                    VALUES
                        (:simkl_id, :tmdb_id, :tvdb_id, :title, :media_type, datetime('now'))
                    ON CONFLICT(simkl_id) DO UPDATE SET
                        tmdb_id    = COALESCE(excluded.tmdb_id, simkl_list_items.tmdb_id),
                        tvdb_id    = COALESCE(excluded.tvdb_id, simkl_list_items.tvdb_id),
                        title      = excluded.title,
                        media_type = excluded.media_type,
                        updated_at = excluded.updated_at
                    """,
                    items,
                )
                membership_rows = [r for r in items if r.get("list_name") is not None]
                if membership_rows:
                    conn.executemany(
                        """
                        INSERT INTO simkl_list_memberships (simkl_id, list_name, list_order)
                        VALUES (:simkl_id, :list_name, :list_order)
                        ON CONFLICT(simkl_id, list_name) DO UPDATE SET
                            list_order = excluded.list_order
                        """,
                        membership_rows,
                    )

    def remove_from_list(self, simkl_ids: list[int], list_name: str) -> None:
        """Remove the given simkl_ids from a specific list."""
        if not simkl_ids:
            return
        placeholders = ",".join("?" * len(simkl_ids))
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    f"DELETE FROM simkl_list_memberships WHERE list_name = ? AND simkl_id IN ({placeholders})",
                    [list_name, *simkl_ids],
                )
        logger.info("Removed %d items from list '%s'.", len(simkl_ids), list_name)

    def query_by_list(self, list_name: str) -> list[sqlite3.Row]:
        """Return items for a list ordered by list_order (for /arr/list)."""
        return self.get_all_for_list(list_name)

    def get_items_missing_ids(self) -> list[sqlite3.Row]:
        """Return all items in at least one list that are missing tmdb_id or tvdb_id."""
        with self._connect() as conn:
            return conn.execute(
                """
                SELECT DISTINCT i.simkl_id, i.tmdb_id, i.tvdb_id, i.title, i.media_type
                FROM simkl_list_items i
                JOIN simkl_list_memberships m ON i.simkl_id = m.simkl_id
                WHERE i.tmdb_id IS NULL OR i.tvdb_id IS NULL
                """
            ).fetchall()

    def list_names_with_counts(self) -> list[sqlite3.Row]:
        """Return each distinct list_name and its item count."""
        with self._connect() as conn:
            return conn.execute(
                "SELECT list_name, COUNT(*) AS count FROM simkl_list_memberships GROUP BY list_name ORDER BY list_name"
            ).fetchall()
