import logging
import time

import tvdb_v4_official

from src.config import Settings

logger = logging.getLogger(__name__)

_REQUEST_DELAY = 0.01  # 10ms between TVDB API calls


class TvdbClient:
    def __init__(self, config: Settings) -> None:
        self._tvdb = tvdb_v4_official.TVDB(config.TVDB_API_KEY)

    def search_tv_by_title(self, title: str, year: int | str | None = None) -> int | None:
        """Search TVDB for a series by title; return tvdb_id or None."""
        time.sleep(_REQUEST_DELAY)
        # TVDB API search fails on & even when URL-encoded; replace with space
        query = title.replace("&", " ")
        try:
            results = self._tvdb.search(query, type="series")
            if not results:
                return None
            if year:
                year_str = str(year)[:4]
                for r in results:
                    if str(r.get("year", ""))[:4] == year_str:
                        return int(r["tvdb_id"])
            return int(results[0]["tvdb_id"])
        except Exception as exc:
            logger.warning("TVDB search failed (title=%r year=%r): %s", title, year, exc)
            return None
