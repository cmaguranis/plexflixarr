import logging

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.config import Settings

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.mdblist.com/rating"
_BATCH_SIZE = 100  # API limit per request

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

    def _fetch_ratings(self, tmdb_ids: list[int], media_type: str, rating: str) -> dict[int, float]:
        """
        Fetch one rating type for a batch of TMDB IDs (up to 200 per call).

        Returns dict of tmdb_id -> rating value.
        Raises MdblistUnavailableError on auth/rate-limit errors.
        """
        scores: dict[int, float] = {}
        for offset in range(0, len(tmdb_ids), _BATCH_SIZE):
            chunk = tmdb_ids[offset : offset + _BATCH_SIZE]
            logger.debug(
                "MDBList batch request: media_type=%s rating=%s ids=%s",
                media_type,
                rating,
                chunk,
            )
            resp = _session.post(
                f"{_BASE_URL}/{media_type}/{rating}",
                params={"apikey": self._api_key},
                json={"ids": chunk, "provider": "tmdb"},
                timeout=15,
            )
            logger.debug(
                "MDBList response: status=%s body=%s",
                resp.status_code,
                resp.text[:500],
            )
            if resp.status_code == 503:
                body = resp.json() if resp.content else {}
                raise MdblistUnavailableError(body.get("error", "503 Service Unavailable"))
            resp.raise_for_status()
            for entry in resp.json().get("ratings", []):
                if entry.get("rating") is not None:
                    scores[entry["id"]] = entry["rating"]
        return scores

    def batch_quality_check(self, tmdb_ids: list[int], media_type: str) -> dict[int, bool]:
        """
        Quality-gate a batch of TMDB IDs for one media type ('movie' or 'show').

        Passes if Trakt score >= MDBLIST_MIN_TRAKT OR Rotten Tomatoes >= MDBLIST_MIN_RATING.
        Items absent from both responses are treated as failing the gate.
        Raises MdblistUnavailableError on auth/rate-limit errors so the caller can fail open.
        """
        trakt = self._fetch_ratings(tmdb_ids, media_type, "trakt")
        tomatoes = self._fetch_ratings(tmdb_ids, media_type, "tomatoes")

        return {
            tmdb_id: (trakt.get(tmdb_id, 0) >= self._min_trakt or tomatoes.get(tmdb_id, 0) >= self._min_rt)
            for tmdb_id in tmdb_ids
        }
