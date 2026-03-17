import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass, field

from src.clients.plex_client import PlexClient
from src.clients.simkl_client.simkl_client import SimklClient
from src.clients.simkl_client.simkl_models import SimklItem, TvSort, YearFilter
from src.clients.tmdb_client import TmdbItem
from src.config import Settings
from src.dummy import create_dummy, ensure_template

logger = logging.getLogger(__name__)

PLACEHOLDER_LABEL = "Placeholder"


@dataclass
class MediaItem:
    title: str
    year: str | None
    media_type: str
    labels: list[str] = field(default_factory=list)
    tmdb_id: int | None = None
    anilist_id: int | None = None
    original_language: str = ""
    genre_ids: list[int] = field(default_factory=list)
    vote_average: float = 0.0
    vote_count: int = 0


# Each entry: (config attribute name for the list name, fetcher callable)
_CURATED_FETCHERS: list[tuple[str, object]] = [
    ("SIMKL_LIST_NAME_KDRAMAS",
     lambda simkl, max, sort, year: simkl.fetch_trending_kdramas(max=max, sort=sort, year=year)),
    ("SIMKL_LIST_NAME_KREALITY",
     lambda simkl, max, sort, year: simkl.fetch_trending_kreality(max=max, sort=sort, year=year)),
    ("SIMKL_LIST_NAME_REALITY",
     lambda simkl, max, sort, year: simkl.fetch_trending_reality(max=max, sort=sort, year=year)),
]


def fetch_curated_lists(
    simkl: SimklClient,
    config: Settings,
    curated_max: int = 100,
    sort: TvSort = TvSort.POPULAR_THIS_WEEK,
    year: YearFilter = YearFilter.THIS_YEAR,
) -> dict[str, Sequence[SimklItem]]:
    """Fetch all curated Simkl lists. Returns {list_name: [SimklItem, ...]}."""
    curated: dict[str, Sequence[SimklItem]] = {}
    for config_attr, fetcher in _CURATED_FETCHERS:
        name = getattr(config, config_attr)
        items = fetcher(simkl, curated_max, sort, year)  # type: ignore[operator]
        logger.info("Fetched %d items for '%s'.", len(items), name)
        curated[name] = items
    return curated


def filter_media(items: list[MediaItem], config: Settings) -> list[MediaItem]:
    """Remove low-quality titles and those already owned in any real Plex library."""
    plex = PlexClient(config)
    all_real_libs = config.REAL_LIBS
    filtered: list[MediaItem] = []

    for item in items:
        if item.original_language and item.original_language in config.EXCLUDED_LANGUAGES:
            logger.debug("Rejected (language=%s): %s", item.original_language, item.title)
            continue

        # TMDB items carry vote data; Trakt/AniList/Simkl items are personalised, skip quality gate
        if (
            item.original_language not in config.QUALITY_GATE_BYPASS_LANGUAGES
            and config.TMDB_QUALITY_GATE
            and item.vote_count > 0
            and (item.vote_count < config.TMDB_MIN_VOTE_COUNT or item.vote_average < config.TMDB_MIN_VOTE_AVERAGE)
        ):
            logger.debug(
                "Rejected (quality, %.1f/%d votes): %s",
                item.vote_average,
                item.vote_count,
                item.title,
            )
            continue

        if plex.exists_in_any(all_real_libs, _base_title(item.title), item.media_type):
            logger.debug("Already in real library, skipping: %s", item.title)
            continue

        filtered.append(item)

    logger.info("%d items passed filters.", len(filtered))
    return filtered


def write_dummies(items: list[MediaItem], config: Settings) -> None:
    """Create dummy .mkv files for each item."""
    ensure_template(config.TEMPLATE_FILE)
    created = 0
    for item in items:
        if create_dummy(item.title, item.year, item.media_type, config, tmdb_id=item.tmdb_id):
            created += 1
    if not created:
        logger.info("No new dummy files created.")


def label_discover_items(items: list[MediaItem], plex: PlexClient, config: Settings) -> None:
    """Find each item in the discover library by TMDB ID and apply Placeholder + any item labels.

    Only operates on items whose file path falls within the configured discover folders,
    so owned content that happens to match a TMDB ID is never accidentally labelled.
    """
    discover_paths = (str(config.DISCOVER_MOVIES_PATH), str(config.DISCOVER_SHOWS_PATH))
    logger.info("Applying labels to %d discover items...", len(items))
    for item in items:
        if item.tmdb_id is None:
            continue
        lib_name, libtype = _lib_and_type(item.media_type, config)
        results = plex.find_by_tmdb_id(lib_name, item.tmdb_id, libtype)
        if not results:
            logger.debug("Not found in Plex: %s (tmdb=%s)", item.title, item.tmdb_id)
            continue
        plex_item = results[0]
        if not any(loc.startswith(discover_paths) for loc in (plex_item.locations or [])):
            logger.debug("Skipping label — not in discover folder: %s", item.title)
            continue
        existing = {lbl.tag for lbl in (plex_item.labels or [])}
        to_add = [lbl for lbl in ([PLACEHOLDER_LABEL] + item.labels) if lbl not in existing]
        if to_add:
            plex.add_labels(plex_item, to_add)


_SEASON_SUFFIX_RE = re.compile(
    r"\s+(?:Season|Part|Cour)\s+\d+.*$"  # "Season 3: ...", "Part 2", "Cour 2"
    r"|\s+\(\d{4}\)\s*$",  # trailing "(2011)"
    re.IGNORECASE,
)


def _base_title(title: str) -> str:
    """Strip trailing season/part/year suffixes for Plex dedup lookups."""
    return _SEASON_SUFFIX_RE.sub("", title).strip()


def _from_tmdb_item(item: TmdbItem) -> MediaItem:
    """Convert a TmdbItem to a MediaItem."""
    return MediaItem(
        title=item.title,
        year=item.year,
        media_type=item.media_type,
        tmdb_id=item.tmdb_id,
        original_language=item.original_language,
        genre_ids=item.genre_ids,
        labels=item.labels,
        vote_average=item.vote_average,
        vote_count=item.vote_count,
    )


def _dedup_by_tmdb_id(
    items: list[MediaItem],
    *,
    merge_labels: bool = False,
    keep_unresolved: bool = False,
) -> list[MediaItem]:
    """Deduplicate items by tmdb_id (first occurrence wins).

    merge_labels: merge labels from duplicate items into the first occurrence.
    keep_unresolved: append items with no tmdb_id to the result unchanged.
    """
    merged: dict[int, MediaItem] = {}
    for item in items:
        if item.tmdb_id is None:
            continue
        if item.tmdb_id in merged:
            if merge_labels:
                existing = merged[item.tmdb_id]
                existing.labels = list(dict.fromkeys(existing.labels + item.labels))
        else:
            merged[item.tmdb_id] = item
    result = list(merged.values())
    if keep_unresolved:
        result += [i for i in items if i.tmdb_id is None]
    return result


def _lib_and_type(media_type: str, config: Settings) -> tuple[str, str]:
    if media_type in ("movie", "movies"):
        return config.DISCOVER_MOVIES_LIB, "movie"
    return config.DISCOVER_SHOWS_LIB, "show"
