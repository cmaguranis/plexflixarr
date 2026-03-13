import logging
from functools import lru_cache

import requests

logger = logging.getLogger(__name__)

_ANIME_LIST_URL = "https://raw.githubusercontent.com/Fribb/anime-lists/master/anime-list-full.json"


@lru_cache(maxsize=1)
def _load_mapping() -> dict[int, int]:
    """Fetch Fribb's anime-lists and return {anilist_id: tmdb_id}."""
    logger.info("Fetching AniList→TMDb ID mapping from Fribb's anime-lists...")
    try:
        resp = requests.get(_ANIME_LIST_URL, timeout=30)
        resp.raise_for_status()
    except Exception as exc:
        logger.warning("Failed to fetch anime-list mapping: %s", exc)
        return {}
    mapping: dict[int, int] = {}
    for entry in resp.json():
        anilist_id = entry.get("anilist_id")
        tmdb_id = entry.get("themoviedb_id")
        if anilist_id and tmdb_id:
            mapping[int(anilist_id)] = int(tmdb_id)
    logger.info("Loaded %d AniList→TMDb mappings.", len(mapping))
    return mapping


def resolve_tmdb_id(anilist_id: int) -> int | None:
    """Return the TMDb ID for the given AniList ID, or None if not found."""
    return _load_mapping().get(anilist_id)
