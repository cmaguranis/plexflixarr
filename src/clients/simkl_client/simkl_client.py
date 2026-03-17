import logging
import time
from typing import TypeVar

import requests

from src.clients.simkl_client.simkl_models import (
    Country,
    MovieGenre,
    MovieSort,
    SimklAnime,
    SimklIds,
    SimklItem,
    SimklMovie,
    SimklShow,
    TrendingSize,
    TrendingTimeframe,
    TvGenre,
    TvNetwork,
    TvSort,
    TvType,
    YearFilter,
)
from src.config import Settings

logger = logging.getLogger(__name__)

_GENRES_BASE = "https://api.simkl.com"
_TRENDING_BASE = "https://data.simkl.in/discover/trending"
_TRENDING_USER_AGENT = "plexflixarr/1.0"
_PAGE_SIZE = 50


T = TypeVar("T", bound=SimklItem)


class SimklRateLimitError(Exception):
    """Raised when all available Simkl API keys are rate limited."""


class SimklClient:
    def __init__(self, config: Settings) -> None:
        keys = [k for k in [config.SIMKL_CLIENT_ID, config.SIMKL_FALLBACK_CLIENT_ID] if k]
        if not keys:
            raise ValueError("SIMKL_CLIENT_ID is not set")
        self._keys = keys
        self._key_index = 0
        self._delay = config.SIMKL_REQUEST_DELAY
        self._headers = {
            "Content-Type": "application/json",
            "simkl-api-key": self._keys[0],
        }

    def _rotate_key(self) -> bool:
        """Switch to the next available API key. Returns False if all keys are exhausted."""
        if self._key_index + 1 < len(self._keys):
            self._key_index += 1
            self._headers["simkl-api-key"] = self._keys[self._key_index]
            logger.warning("Simkl rate limited — rotated to key index %d", self._key_index)
            return True
        return False

    # ------------------------------------------------------------------
    # Browse / genres
    # ------------------------------------------------------------------

    def fetch_tv(
        self,
        genre: TvGenre = TvGenre.ALL,
        type: TvType = TvType.ALL,
        country: Country = Country.ALL,
        network: TvNetwork = TvNetwork.ALL,
        year: YearFilter | int = YearFilter.ALL,
        sort: TvSort = TvSort.RANK,
        max: int = 100,
    ) -> list[SimklShow]:
        """Fetch TV shows from /tv/genres with full filter support.

        country and network segments are omitted from the path when set to ALL,
        matching the Simkl API's optional segment convention.
        """
        if genre == TvGenre.ALL:
            segments = [str(type)]
        else:
            segments = [str(genre), str(type)]
        if country != Country.ALL:
            segments.append(str(country))
        if network != TvNetwork.ALL:
            segments.append(str(network))
        segments.extend([str(year), str(sort)])
        path = "/tv/genres/" + "/".join(segments)
        logger.info(f"Fetching using {path}")
        return self._fetch_genres_pages(path, SimklShow, max)

    def fetch_movies(
        self,
        genre: MovieGenre = MovieGenre.ALL,
        type: str = "all-types",
        country: Country = Country.ALL,
        year: YearFilter | int = YearFilter.ALL,
        sort: MovieSort = MovieSort.RANK,
        max: int = 100,
    ) -> list[SimklMovie]:
        """Fetch movies from /movies/genres with full filter support."""
        path = f"/movies/genres/{genre}/{type}/{country}/{str(year)}/{sort}"
        return self._fetch_genres_pages(path, SimklMovie, max)

    def fetch_trending_kdramas(
        self,
        max: int = 100,
        sort: TvSort = TvSort.POPULAR_THIS_WEEK,
        year: YearFilter = YearFilter.THIS_YEAR,
    ) -> list[SimklShow]:
        """Fetch trending Korean dramas."""
        path = f"/tv/genres/all/kr/{year}/{sort}/"
        logger.info(f"Fetching Kdramas using {path}")
        return self._fetch_genres_pages(path, SimklShow, max)

    def fetch_trending_kreality(
        self,
        max: int = 100,
        sort: TvSort = TvSort.POPULAR_THIS_WEEK,
        year: YearFilter = YearFilter.THIS_YEAR,
    ) -> list[SimklShow]:
        """Fetch trending Korean reality/variety shows."""
        path = f"/tv/genres/reality/all-types/kr/{year}/{sort}/"
        logger.info(f"Fetching Korean reality using {path}")
        return self._fetch_genres_pages(path, SimklShow, max)

    def fetch_trending_reality(
        self,
        max: int = 100,
        sort: TvSort = TvSort.POPULAR_THIS_WEEK,
        year: YearFilter = YearFilter.THIS_YEAR,
    ) -> list[SimklShow]:
        """Fetch trending reality/entertainment globally."""
        path = f"/tv/genres/reality/all-types/{year}/{sort}/"
        logger.info(f"Fetching Reality using {path}")
        return self._fetch_genres_pages(path, SimklShow, max)

    # ------------------------------------------------------------------
    # Trending files (CDN, no auth required)
    # ------------------------------------------------------------------

    def fetch_trending_movies(
        self,
        timeframe: TrendingTimeframe = TrendingTimeframe.WEEK,
        size: TrendingSize = TrendingSize.TOP_100,
    ) -> list[SimklMovie]:
        """Fetch pre-built trending movies JSON (today / week / month)."""
        return self._fetch_trending_file(f"movies/{timeframe}_{size.value}.json", SimklMovie)

    def fetch_trending_tv(
        self,
        timeframe: TrendingTimeframe = TrendingTimeframe.WEEK,
        size: TrendingSize = TrendingSize.TOP_100,
    ) -> list[SimklShow]:
        """Fetch pre-built trending TV shows JSON (today / week / month)."""
        return self._fetch_trending_file(f"tv/{timeframe}_{size.value}.json", SimklShow)

    def fetch_trending_anime(
        self,
        timeframe: TrendingTimeframe = TrendingTimeframe.WEEK,
        size: TrendingSize = TrendingSize.TOP_100,
    ) -> list[SimklAnime]:
        """Fetch pre-built trending anime JSON (today / week / month)."""
        return self._fetch_trending_file(f"anime/{timeframe}_{size.value}.json", SimklAnime)

    # ------------------------------------------------------------------
    # ID lookup
    # ------------------------------------------------------------------

    def lookup_ids_by_simkl_id(self, simkl_id: int, media_type: str = "shows") -> SimklIds | None:
        """Return full IDs (including TMDB) for a Simkl item via /search/id.

        Raises SimklRateLimitError when all available API keys are exhausted.
        """
        url = f"{_GENRES_BASE}/search/id?simkl={simkl_id}&type={media_type}"
        logger.debug("Simkl ID lookup: GET %s", url)
        while True:
            try:
                resp = requests.get(url, headers=self._headers, timeout=10)
                if resp.status_code == 429:
                    if not self._rotate_key():
                        raise SimklRateLimitError("All Simkl API keys are rate limited")
                    continue
                resp.raise_for_status()
                data = resp.json() or []
                if data and isinstance(data[0], dict):
                    obj = data[0]
                    nested = obj.get("show") or obj.get("movie") or obj
                    return SimklIds.model_validate(nested.get("ids", {}))
                return None
            except SimklRateLimitError:
                raise
            except Exception as exc:
                logger.warning("Simkl ID lookup failed (simkl_id=%d): %s", simkl_id, exc)
                return None

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _fetch_genres_pages(
        self,
        path: str,
        model_cls: type[T],
        max: int,
    ) -> list[T]:
        results: list[T] = []
        page = 1
        while len(results) < max:
            page_items = self._fetch_genres_page(path, page, _PAGE_SIZE, model_cls)
            results.extend(page_items)
            if len(page_items) < _PAGE_SIZE or len(results) >= max:
                break
            page += 1
            time.sleep(self._delay)
        return results

    def _fetch_genres_page(self, path: str, page: int, limit: int, model_cls: type[T]) -> list[T]:
        url = f"{_GENRES_BASE}{path}?page={page}&limit={limit}"
        logger.debug("Simkl genres request: GET %s", url)
        try:
            resp = requests.get(url, headers=self._headers, timeout=10)
            resp.raise_for_status()
            data = resp.json() or []
            if isinstance(data, dict):
                # Some endpoints return sectioned results (e.g. top_last_aired, premieres)
                data = [item for section in data.values() if isinstance(section, list) for item in section]
            return [model_cls.model_validate(item) for item in data if isinstance(item, dict)]
        except Exception as exc:
            logger.warning("Simkl genres fetch failed (%s page=%d): %s", path, page, exc)
            return []

    def _fetch_trending_file(self, filename: str, model_cls: type[T]) -> list[T]:
        url = f"{_TRENDING_BASE}/{filename}"
        headers = {**self._headers, "User-Agent": _TRENDING_USER_AGENT}
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            return [model_cls.model_validate(item) for item in (resp.json() or [])]
        except Exception as exc:
            logger.warning("Simkl trending fetch failed (%s): %s", filename, exc)
            return []
