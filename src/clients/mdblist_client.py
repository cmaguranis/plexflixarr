import logging

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.config import Settings

logger = logging.getLogger(__name__)

_BASE_URL = "https://mdblist.com/api/"

# Free tier: 1,000 lookup checks per day.
# With 4 providers × 5 pages × 20 results × 2 types = 800 checks per night,
# this stays within the limit. The caller is responsible for sleeping 1s between calls.

# Retry only on genuine transient errors — not 503, which MDBList uses for rate limiting.
_retry = Retry(total=3, backoff_factor=2, status_forcelist=[429, 500, 502, 504])
_adapter = HTTPAdapter(max_retries=_retry)
_session = requests.Session()
_session.mount("https://", _adapter)


class MdblistUnavailableError(Exception):
    """Raised when MDBList returns an auth or rate-limit error."""


class MdblistClient:
    def __init__(self, config: Settings) -> None:
        self._api_key = config.MDBLIST_API_KEY
        self._min_trakt = config.MDBLIST_MIN_TRAKT
        self._min_rt = config.MDBLIST_MIN_RATING

    def passes_quality_check(self, tmdb_id: int, media_type: str) -> bool:
        """
        Return True if the item meets the configured rating thresholds.

        Accepts if Trakt score >= MDBLIST_MIN_TRAKT OR Rotten Tomatoes >= MDBLIST_MIN_RATING.
        Raises MdblistUnavailableError on auth/rate-limit errors so the caller can fail open.
        'media_type' should be 'movie' or 'tv'; MDBList expects 'movie' or 'show'.
        """
        m_type = "movie" if media_type == "movie" else "show"
        try:
            resp = _session.get(
                _BASE_URL,
                params={"apikey": self._api_key, "tmdb": tmdb_id, "m": m_type},
                timeout=10,
            )

            # MDBList signals rate-limit / invalid key via 503 with a JSON error body.
            if resp.status_code == 503:
                body = resp.json() if resp.content else {}
                raise MdblistUnavailableError(body.get("error", "503 Service Unavailable"))

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

        except MdblistUnavailableError:
            raise
        except Exception as exc:
            logger.warning("MDBList check failed (tmdb_id=%s): %s — skipping item", tmdb_id, exc)
            return False
