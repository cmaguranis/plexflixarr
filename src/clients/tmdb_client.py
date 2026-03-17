import logging
import math
import time
from dataclasses import dataclass, field
from datetime import date, timedelta

import tmdbsimple as tmdb

from src.config import Settings

logger = logging.getLogger(__name__)

_WATCH_REGION = "US"


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
        tmdb.API_KEY = config.TMDB_API_KEY
        self._providers = config.STREAMING_PROVIDERS
        self._delay = config.TMDB_REQUEST_DELAY

    # -------------------------------------------------------------------------
    # Ingestion helpers (existing interface)
    # -------------------------------------------------------------------------

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
                        results.append(self._make_item(item, media_type, labels=[label]))
                    time.sleep(self._delay)

        return results

    def fetch_trending(self, pages: int = 1) -> list[TmdbItem]:
        """Fetch globally trending movies and TV shows from TMDB (weekly window)."""
        results: list[TmdbItem] = []

        for media_type in ("movie", "tv"):
            for page in range(1, pages + 1):
                try:
                    response = tmdb.Trending(media_type, "week").info(page=page)
                    for item in response.get("results", []):
                        results.append(self._make_item(item, media_type, labels=["Discover_Trending"]))
                except Exception as exc:
                    logger.warning("TMDB trending fetch failed (type=%s page=%d): %s", media_type, page, exc)
                time.sleep(self._delay)

        return results

    # -------------------------------------------------------------------------
    # Trending (daily)
    # -------------------------------------------------------------------------

    def get_trending_movies(self, n: int = 100) -> list[TmdbItem]:
        """Top n trending movies today."""
        return self._fetch_trending("movie", n)

    def get_trending_shows(self, n: int = 100) -> list[TmdbItem]:
        """Top n trending TV shows today."""
        return self._fetch_trending("tv", n)

    # -------------------------------------------------------------------------
    # Discover — popular over last m days
    # -------------------------------------------------------------------------

    def get_popular_movies(self, n: int = 100, days: int = 365) -> list[TmdbItem]:
        """Top n popular movies released within the last `days` days."""
        return self._fetch_discover("movie", n, **_date_filter("movie", days))

    def get_popular_shows(self, n: int = 100, days: int = 365) -> list[TmdbItem]:
        """Top n popular TV shows that started airing within the last `days` days."""
        return self._fetch_discover("tv", n, **_date_filter("tv", days))

    def get_popular_korean_movies(self, n: int = 100, days: int = 365) -> list[TmdbItem]:
        """Top n popular Korean-language movies released within the last `days` days."""
        return self._fetch_discover("movie", n, with_original_language="ko", **_date_filter("movie", days))

    def get_popular_korean_shows(self, n: int = 100, days: int = 365) -> list[TmdbItem]:
        """Top n popular Korean-language TV shows that started airing within the last `days` days."""
        return self._fetch_discover("tv", n, with_original_language="ko", **_date_filter("tv", days))

    def search_tv_by_title(self, title: str, year: int | str | None = None) -> int | None:
        """Search TMDB for a TV show by title, return tmdb_id or None."""
        try:
            params: dict = {"query": title}
            if year:
                params["first_air_date_year"] = str(year)[:4]
            response = tmdb.Search().tv(**params)
            results = response.get("results", [])
            if results:
                return results[0]["id"]
        except Exception as exc:
            logger.warning("TMDB TV search failed (title=%r year=%r): %s", title, year, exc)
        return None

    # -------------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------------

    def _fetch_trending(self, media_type: str, n: int) -> list[TmdbItem]:
        results: list[TmdbItem] = []
        for page in range(1, math.ceil(n / 20) + 1):
            try:
                response = tmdb.Trending(media_type, "day").info(page=page)
                for item in response.get("results", []):
                    results.append(self._make_item(item, media_type))
                    if len(results) >= n:
                        return results
            except Exception as exc:
                logger.warning("TMDB trending fetch failed (type=%s page=%d): %s", media_type, page, exc)
            time.sleep(self._delay)
        return results

    def _fetch_discover(self, media_type: str, n: int, **kwargs) -> list[TmdbItem]:
        results: list[TmdbItem] = []
        for page in range(1, math.ceil(n / 20) + 1):
            try:
                discover = tmdb.Discover()
                params = {"sort_by": "popularity.desc", "page": page, **kwargs}
                response = discover.movie(**params) if media_type == "movie" else discover.tv(**params)
                for item in response.get("results", []):
                    results.append(self._make_item(item, media_type))
                    if len(results) >= n:
                        return results
            except Exception as exc:
                logger.warning("TMDB discover fetch failed (type=%s page=%d): %s", media_type, page, exc)
            time.sleep(self._delay)
        return results

    def _fetch_page(self, provider_id: str, media_type: str, page: int) -> list[dict]:
        try:
            discover = tmdb.Discover()
            kwargs = {
                "watch_region": _WATCH_REGION,
                "with_watch_providers": provider_id,
                "sort_by": "popularity.desc",
                "page": page,
            }
            response = discover.movie(**kwargs) if media_type == "movie" else discover.tv(**kwargs)
            return response.get("results", [])
        except Exception as exc:
            logger.warning(
                "TMDB fetch failed (provider=%s type=%s page=%d): %s",
                provider_id,
                media_type,
                page,
                exc,
            )
            return []

    @staticmethod
    def _make_item(raw: dict, media_type: str, labels: list[str] | None = None) -> TmdbItem:
        return TmdbItem(
            title=raw.get("title", "") if media_type == "movie" else raw.get("name", ""),
            year=(raw.get("release_date", "") or "")[:4]
            if media_type == "movie"
            else (raw.get("first_air_date", "") or "")[:4],
            media_type=media_type,
            tmdb_id=raw["id"],
            original_language=raw.get("original_language", ""),
            labels=list(labels) if labels else [],
            genre_ids=raw.get("genre_ids", []),
            vote_average=raw.get("vote_average", 0.0),
            vote_count=raw.get("vote_count", 0),
        )


def _date_filter(media_type: str, days: int) -> dict:
    today = date.today()
    since = (today - timedelta(days=days)).isoformat()
    until = today.isoformat()
    if media_type == "movie":
        return {"primary_release_date.gte": since, "primary_release_date.lte": until}
    return {"first_air_date.gte": since, "first_air_date.lte": until}
