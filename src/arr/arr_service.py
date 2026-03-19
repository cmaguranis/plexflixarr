from collections.abc import Sequence

from src.clients.plex_client import PlexClient
from src.clients.simkl_client.simkl_models import SimklIds, SimklItem
from src.config import Settings
from src.db.simkl_lists import SimklListDB


def get_list_names_with_counts(config: Settings) -> list[dict]:
    db = SimklListDB(config.SIMKL_LISTS_DB_FILE)
    db.init_db()
    return [{"name": row["list_name"], "count": row["count"]} for row in db.list_names_with_counts()]


def get_list_items(name: str, config: Settings, service: str | None = None) -> list[dict]:
    db = SimklListDB(config.SIMKL_LISTS_DB_FILE)
    db.init_db()
    rows = db.query_by_list(name)
    if service == "sonarr":
        return [
            {"Title": row["title"], "TvdbId": row["tvdb_id"]}
            for row in rows
            if row["tvdb_id"] is not None
        ]
    if service == "radarr":
        return [
            {"Title": row["title"], "TmdbId": row["tmdb_id"]}
            for row in rows
            if row["tmdb_id"] is not None
        ]
    return [
        {
            "Title": row["title"],
            "TvdbId": row["tvdb_id"],
            "TmdbId": row["tmdb_id"] or 0,
        }
        for row in rows
        if (row["media_type"] == "movie" and row["tmdb_id"] is not None)
        or (row["media_type"] != "movie" and row["tvdb_id"] is not None)
    ]


def build_curated_collections(config: Settings) -> dict:
    db = SimklListDB(config.SIMKL_LISTS_DB_FILE)
    db.init_db()

    curated_names = [
        config.SIMKL_LIST_NAME_KDRAMAS,
        config.SIMKL_LIST_NAME_KREALITY,
        config.SIMKL_LIST_NAME_REALITY,
        config.SIMKL_LIST_NAME_KMOVIES,
    ]

    curated: dict[str, Sequence[SimklItem]] = {}
    for name in curated_names:
        rows = db.query_by_list(name)
        curated[name] = [
            SimklItem(
                title=row["title"],
                ids=SimklIds(simkl=row["simkl_id"], tmdb=row["tmdb_id"], tvdb=row["tvdb_id"]),
            )
            for row in rows
        ]

    plex = PlexClient(config)
    movie_lists = {config.SIMKL_LIST_NAME_KMOVIES}
    plex.create_curated_collections(config, curated, movie_lists=movie_lists)
    return {"status": "ok", "lists": {name: len(items) for name, items in curated.items()}}
