import logging
import time
from dataclasses import dataclass, field

import requests

from src.config import Settings

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.themoviedb.org/3/discover"
_TRENDING_URL = "https://api.themoviedb.org/3/trending"
_WATCH_REGION = "US"
_REQUEST_DELAY = 0.5  # seconds between TMDB requests


@dataclass
class TmdbItem:
    title: str
    year: str
    media_type: str  # 'movie' or 'tv'
    tmdb_id: int
    original_language: str = ""
    labels: list[str] = field(default_factory=list)
    genre_ids: list[int] = field(default_factory=list)
    vote_average: float = 0.0
    vote_count: int = 0


class TmdbClient:
    def __init__(self, config: Settings) -> None:
        self._api_key = config.TMDB_API_KEY
        self._providers = config.STREAMING_PROVIDERS

    def fetch_streaming(self, pages: int = 5) -> list[TmdbItem]:
        """
        Fetch trending streaming content from TMDB for each configured provider.

        Returns up to (pages × 20) items per provider per media type.
        Each item carries the provider label and tmdb_id for downstream quality filtering.
        """
        results: list[TmdbItem] = []

        for provider_id, label in self._providers.items():
            for media_type in ("movie", "tv"):
                for page in range(1, pages + 1):
                    items = self._fetch_page(provider_id, media_type, page)
                    for item in items:
                        results.append(
                            TmdbItem(
                                title=item.get("title")
                                if media_type == "movie"
                                else item.get("name", ""),
                                year=(item.get("release_date", "") or "")[:4]
                                if media_type == "movie"
                                else (item.get("first_air_date", "") or "")[:4],
                                media_type=media_type,
                                tmdb_id=item["id"],
                                original_language=item.get("original_language", ""),
                                labels=[label],
                                genre_ids=item.get("genre_ids", []),
                                vote_average=item.get("vote_average", 0.0),
                                vote_count=item.get("vote_count", 0),
                            )
                        )
                    time.sleep(_REQUEST_DELAY)

        return results

    def fetch_trending(self, pages: int = 1) -> list[TmdbItem]:
        """Fetch globally trending movies and TV shows from TMDB (weekly window)."""
        results: list[TmdbItem] = []

        for media_type in ("movie", "tv"):
            for page in range(1, pages + 1):
                url = (
                    f"{_TRENDING_URL}/{media_type}/week"
                    f"?api_key={self._api_key}"
                    f"&page={page}"
                )
                try:
                    resp = requests.get(url, timeout=10)
                    resp.raise_for_status()
                    for item in resp.json().get("results", []):
                        results.append(
                            TmdbItem(
                                title=item.get("title") if media_type == "movie" else item.get("name", ""),
                                year=(item.get("release_date", "") or "")[:4]
                                if media_type == "movie"
                                else (item.get("first_air_date", "") or "")[:4],
                                media_type=media_type,
                                tmdb_id=item["id"],
                                original_language=item.get("original_language", ""),
                                labels=["Discover_Trending"],
                                genre_ids=item.get("genre_ids", []),
                                vote_average=item.get("vote_average", 0.0),
                                vote_count=item.get("vote_count", 0),
                            )
                        )
                except Exception as exc:
                    logger.warning("TMDB trending fetch failed (type=%s page=%d): %s", media_type, page, exc)
                time.sleep(_REQUEST_DELAY)

        return results

    def _fetch_page(self, provider_id: str, media_type: str, page: int) -> list[dict]:
        url = (
            f"{_BASE_URL}/{media_type}"
            f"?api_key={self._api_key}"
            f"&watch_region={_WATCH_REGION}"
            f"&with_watch_providers={provider_id}"
            f"&sort_by=popularity.desc"
            f"&page={page}"
        )
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            return resp.json().get("results", [])
        except Exception as exc:
            logger.warning(
                "TMDB fetch failed (provider=%s type=%s page=%d): %s",
                provider_id,
                media_type,
                page,
                exc,
            )
            return []
