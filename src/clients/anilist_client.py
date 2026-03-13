import logging
import time
from dataclasses import dataclass

import requests

from src.config import Settings

logger = logging.getLogger(__name__)

_GRAPHQL_URL = "https://graphql.anilist.co"
_REQUEST_DELAY = 1  # seconds between AniList requests

_RECOMMENDATIONS_QUERY = """
query ($userName: String, $perPage: Int) {
  MediaListCollection(userName: $userName, type: ANIME, status: COMPLETED, sort: SCORE_DESC) {
    lists {
      entries {
        media {
          title { english romaji }
          recommendations(sort: RATING_DESC, perPage: $perPage) {
            nodes {
              mediaRecommendation {
                title { english romaji }
                seasonYear
                format
              }
            }
          }
        }
      }
    }
  }
}
"""

_TRENDING_QUERY = """
query ($page: Int, $perPage: Int) {
  Page(page: $page, perPage: $perPage) {
    media(type: ANIME, sort: TRENDING_DESC) {
      title { english romaji }
      seasonYear
      format
    }
  }
}
"""

# AniList format → our media_type. Formats not in this map (MUSIC, MANGA, etc.) are skipped.
_FORMAT_TO_MEDIA_TYPE: dict[str, str] = {
    "MOVIE": "movie",
    "TV": "show",
    "TV_SHORT": "show",
    "ONA": "show",
    "OVA": "show",
    "SPECIAL": "show",
}


@dataclass
class AniListItem:
    title: str
    year: str | None
    media_type: str  # 'movie' or 'show'


class AniListClient:
    def __init__(self, config: Settings) -> None:
        self._config = config

    def fetch_recommendations(self, username: str) -> list[AniListItem]:
        """
        Fetch personalised anime recommendations from AniList.

        Fetches the user's COMPLETED anime sorted by personal score (highest first),
        then for each title retrieves the top ANILIST_RECS_PER_ENTRY community-rated
        recommendations. Results are deduplicated so each recommended title appears once.
        No auth required — uses the public userName API.
        """
        try:
            resp = requests.post(
                _GRAPHQL_URL,
                json={
                    "query": _RECOMMENDATIONS_QUERY,
                    "variables": {"userName": username, "perPage": self._config.ANILIST_RECS_PER_ENTRY},
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.warning("AniList recommendations fetch failed (user=%s): %s", username, exc)
            return []
        time.sleep(_REQUEST_DELAY)

        seen: set[str] = set()
        results: list[AniListItem] = []

        for lst in (data.get("data") or {}).get("MediaListCollection", {}).get("lists", []):
            for entry in lst.get("entries", []):
                for node in entry.get("media", {}).get("recommendations", {}).get("nodes", []):
                    rec = node.get("mediaRecommendation")
                    if not rec:
                        continue
                    media_type = _FORMAT_TO_MEDIA_TYPE.get(rec.get("format"))
                    if media_type is None:
                        continue
                    title = rec["title"].get("english") or rec["title"].get("romaji")
                    if not title:
                        continue
                    year = rec.get("seasonYear")
                    key = f"{title}|{year}"
                    if key in seen:
                        continue
                    seen.add(key)
                    results.append(AniListItem(
                        title=title,
                        year=str(year) if year else None,
                        media_type=media_type,
                    ))

        return results

    def fetch_trending(self, pages: int = 2, per_page: int = 50) -> list[AniListItem]:
        """
        Fetch currently trending anime from AniList (no auth required).

        Queries AniList's global trending chart sorted by TRENDING_DESC,
        covering both TV series and movies. Results are deduplicated.
        """
        seen: set[str] = set()
        results: list[AniListItem] = []

        for page in range(1, pages + 1):
            try:
                resp = requests.post(
                    _GRAPHQL_URL,
                    json={
                        "query": _TRENDING_QUERY,
                        "variables": {"page": page, "perPage": per_page},
                    },
                    timeout=30,
                )
                resp.raise_for_status()
                data = resp.json()
            except Exception as exc:
                logger.warning("AniList trending fetch failed (page=%d): %s", page, exc)
                break
            time.sleep(_REQUEST_DELAY)

            for media in (data.get("data") or {}).get("Page", {}).get("media", []):
                media_type = _FORMAT_TO_MEDIA_TYPE.get(media.get("format"))
                if media_type is None:
                    continue
                title = media["title"].get("english") or media["title"].get("romaji")
                if not title:
                    continue
                year = media.get("seasonYear")
                key = f"{title}|{year}"
                if key in seen:
                    continue
                seen.add(key)
                results.append(AniListItem(
                    title=title,
                    year=str(year) if year else None,
                    media_type=media_type,
                ))

        return results
