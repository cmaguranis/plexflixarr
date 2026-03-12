import logging

import requests

from src.config import Settings

logger = logging.getLogger(__name__)

_BASE_URL = "https://mdblist.com/api/"

# Free tier: 1,000 lookup checks per day.
# With 4 providers × 5 pages × 20 results × 2 types = 800 checks per night,
# this stays within the limit. The caller is responsible for sleeping 1s between calls.


class MdblistClient:
    def __init__(self, config: Settings) -> None:
        self._api_key = config.MDBLIST_API_KEY
        self._min_trakt = config.MDBLIST_MIN_TRAKT
        self._min_rt = config.MDBLIST_MIN_RT

    def passes_quality_check(self, tmdb_id: int, media_type: str) -> bool:
        """
        Return True if the item meets the configured rating thresholds.

        Accepts if Trakt score >= MDBLIST_MIN_TRAKT OR Rotten Tomatoes >= MDBLIST_MIN_RT.
        Returns False on API error so low-quality items are not silently admitted.
        'media_type' should be 'movie' or 'tv'; MDBList expects 'movie' or 'show'.
        """
        m_type = "movie" if media_type == "movie" else "show"
        try:
            resp = requests.get(
                _BASE_URL,
                params={"apikey": self._api_key, "tmdb": tmdb_id, "m": m_type},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()

            if "error" in data:
                # Item not found on MDBList yet — skip it
                logger.debug("MDBList: item not found (tmdb_id=%s)", tmdb_id)
                return False

            for rating in data.get("ratings", []):
                source = rating.get("source")
                value = rating.get("value") or 0
                if source == "trakt" and value >= self._min_trakt:
                    return True
                if source == "tomatoes" and value >= self._min_rt:
                    return True

            return False

        except Exception as exc:
            logger.warning("MDBList check failed (tmdb_id=%s): %s — skipping item", tmdb_id, exc)
            return False
