import logging
import time
from dataclasses import dataclass

import requests

from src.config import Settings

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.trakt.tv"
_REQUEST_DELAY = 1  # seconds between Trakt requests

# Couchmoney generates personalised recommendation lists under its own account.
# After logging into couchmoney.tv with your Trakt account, check your Trakt
# profile → Lists for the exact slugs. These are the typical defaults.
_DEFAULT_SLUGS = ["recommendations-movies", "recommendations-shows"]


@dataclass
class TraktItem:
    title: str
    year: str | None
    media_type: str  # 'movie' or 'show'


class TraktClient:
    def __init__(self, config: Settings) -> None:
        self._headers = {
            "Content-Type": "application/json",
            "trakt-api-version": "2",
            "trakt-api-key": config.TRAKT_CLIENT_ID,
        }

    def fetch_recommendations(self, slugs: list[str] | None = None) -> list[TraktItem]:
        """
        Fetch items from Couchmoney recommendation lists on Trakt.

        Slugs default to the standard Couchmoney list names. Override via argument
        if your lists have different names.
        """
        slugs = slugs or _DEFAULT_SLUGS
        results: list[TraktItem] = []

        for slug in slugs:
            url = f"{_BASE_URL}/users/couchmoney/lists/{slug}/items"
            try:
                resp = requests.get(url, headers=self._headers, timeout=10)
                resp.raise_for_status()
                for entry in resp.json():
                    m_type = entry.get("type")  # 'movie' or 'show'
                    media_data = entry.get(m_type, {})
                    results.append(
                        TraktItem(
                            title=media_data.get("title", ""),
                            year=str(media_data["year"]) if media_data.get("year") else None,
                            media_type=m_type,
                        )
                    )
            except Exception as exc:
                logger.warning("Trakt fetch failed (slug=%s): %s", slug, exc)
            time.sleep(_REQUEST_DELAY)

        return results
