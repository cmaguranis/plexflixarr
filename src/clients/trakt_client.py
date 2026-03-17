import logging
import time
from dataclasses import dataclass, field

import requests

from src.config import Settings

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.trakt.tv"
_REQUEST_DELAY = 1  # seconds between Trakt requests

# Couchmoney generates personalised recommendation lists on the user's own Trakt account.
# After logging into couchmoney.tv with your Trakt account, check your Trakt
# profile → Lists for the exact slugs. These are the typical defaults.
_DEFAULT_SLUGS = ["movies-recommendations-couchmoney-tv", "tv-recommendations-couchmoney-tv"]

# Couchmoney sets this string in each themed list's description field.
_COUCHMONEY_DESCRIPTION_MARKER = "couchmoney"


@dataclass
class TraktItem:
    title: str
    year: str | None
    media_type: str  # 'movie' or 'show'
    tmdb_id: int | None = None


@dataclass
class TraktList:
    slug: str
    display_name: str
    items: list[TraktItem] = field(default_factory=list)


class TraktClient:
    def __init__(self, config: Settings) -> None:
        self._headers = {
            "Content-Type": "application/json",
            "trakt-api-version": "2",
            "trakt-api-key": config.TRAKT_CLIENT_ID,
        }

    def fetch_recommendations(self, username: str, slugs: list[str] | None = None) -> list[TraktItem]:
        """
        Fetch items from Couchmoney recommendation lists on the user's Trakt account.

        Slugs default to the standard Couchmoney list names. Override via argument
        if your lists have different names.
        """
        slugs = slugs or _DEFAULT_SLUGS
        results: list[TraktItem] = []

        for slug in slugs:
            url = f"{_BASE_URL}/users/{username}/lists/{slug}/items"
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
                            tmdb_id=media_data.get("ids", {}).get("tmdb"),
                        )
                    )
            except Exception as exc:
                logger.warning("Trakt fetch failed (slug=%s): %s", slug, exc)
            time.sleep(_REQUEST_DELAY)

        return results

    def fetch_couchmoney_lists(self, username: str) -> list[TraktList]:
        """
        Discover and fetch all Couchmoney-generated themed lists from the user's Trakt account.

        Identifies Couchmoney lists by checking for 'couchmoney' in the list description.
        The standard recommendations-movies/shows slugs are excluded — they are handled
        separately by fetch_recommendations() and shown as the "Recommended for Me" row.
        """
        url = f"{_BASE_URL}/users/{username}/lists"
        try:
            resp = requests.get(url, headers=self._headers, timeout=10)
            resp.raise_for_status()
            all_lists = resp.json()
        except Exception as exc:
            logger.warning("Failed to fetch Trakt lists for user %s: %s", username, exc)
            return []

        themed = [
            lst
            for lst in all_lists
            if _COUCHMONEY_DESCRIPTION_MARKER in lst.get("description", "").lower()
            and lst["ids"]["slug"] not in _DEFAULT_SLUGS
        ]
        logger.info("Found %d Couchmoney themed lists for %s.", len(themed), username)

        results: list[TraktList] = []
        for lst_meta in themed:
            slug = lst_meta["ids"]["slug"]
            items = self._fetch_list_items(username, slug)
            results.append(
                TraktList(
                    slug=slug,
                    display_name=lst_meta["name"],
                    items=items,
                )
            )
            time.sleep(_REQUEST_DELAY)

        return results

    def _fetch_list_items(self, username: str, slug: str) -> list[TraktItem]:
        url = f"{_BASE_URL}/users/{username}/lists/{slug}/items"
        try:
            resp = requests.get(url, headers=self._headers, timeout=10)
            resp.raise_for_status()
            items = []
            for entry in resp.json():
                m_type = entry.get("type")
                media_data = entry.get(m_type, {})
                items.append(
                    TraktItem(
                        title=media_data.get("title", ""),
                        year=str(media_data["year"]) if media_data.get("year") else None,
                        media_type=m_type,
                        tmdb_id=media_data.get("ids", {}).get("tmdb"),
                    )
                )
            return items
        except Exception as exc:
            logger.warning("Failed to fetch items for list %s: %s", slug, exc)
            return []
