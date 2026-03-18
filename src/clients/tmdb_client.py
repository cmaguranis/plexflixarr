import logging

import tmdbsimple as tmdb

from src.config import Settings

logger = logging.getLogger(__name__)


class TmdbClient:
    def __init__(self, config: Settings) -> None:
        tmdb.API_KEY = config.TMDB_API_KEY
        self._delay = config.TMDB_REQUEST_DELAY

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
