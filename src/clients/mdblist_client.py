import logging

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.config import Settings

logger = logging.getLogger(__name__)

_API_BASE = "https://api.mdblist.com"
_BASE_URL = f"{_API_BASE}/rating"
_BATCH_SIZE = 100  # API limit per request
_LIST_ITEM_BATCH_SIZE = 200

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
        self._username = config.MDBLIST_USERNAME
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

    # -------------------------------------------------------------------------
    # List management
    # -------------------------------------------------------------------------

    def get_user_lists(self) -> list[dict]:
        """Return all lists owned by the configured user."""
        resp = _session.get(
            f"{_API_BASE}/lists/user/{self._username}",
            params={"apikey": self._api_key},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()

    def find_list_by_name(self, name: str) -> dict | None:
        """Return the first list whose name matches exactly, or None."""
        for lst in self.get_user_lists():
            if lst.get("name") == name:
                return lst
        return None

    def delete_list(self, list_id: int) -> None:
        """Permanently delete a list by ID."""
        resp = _session.delete(
            f"{_API_BASE}/lists/{list_id}",
            params={"apikey": self._api_key},
            timeout=15,
        )
        resp.raise_for_status()
        logger.info("Deleted MDBList list %d.", list_id)

    def create_list(self, name: str) -> int:
        """Create a new list and return its ID."""
        resp = _session.post(
            f"{_API_BASE}/lists/user/add",
            params={"apikey": self._api_key},
            json={"name": name, "private": False},
            timeout=15,
        )
        resp.raise_for_status()
        list_id: int = resp.json()["id"]
        logger.info("Created MDBList list '%s' (id=%d).", name, list_id)
        return list_id

    def add_items_to_list(self, list_id: int, movies: list[dict], shows: list[dict]) -> None:
        """Add items to a list in batches of 200.

        movies: [{"tmdb": <int>}, ...]
        shows:  [{"tmdb": <int>}, ...]
        """
        all_items = [("movies", movies), ("shows", shows)]
        for media_key, items in all_items:
            for i in range(0, len(items), _LIST_ITEM_BATCH_SIZE):
                batch = items[i : i + _LIST_ITEM_BATCH_SIZE]
                resp = _session.post(
                    f"{_API_BASE}/lists/{list_id}/items/add",
                    params={"apikey": self._api_key},
                    json={media_key: batch},
                    timeout=15,
                )
                resp.raise_for_status()
                logger.debug("Added batch of %d %s to MDBList list %d.", len(batch), media_key, list_id)
        logger.info("Added %d movies, %d shows to MDBList list %d.", len(movies), len(shows), list_id)

    # -------------------------------------------------------------------------
    # Quality checking
    # -------------------------------------------------------------------------

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
