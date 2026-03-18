import logging
from collections.abc import Sequence

from src.clients.simkl_client.simkl_client import SimklClient
from src.clients.simkl_client.simkl_models import SimklItem, TvSort, YearFilter
from src.config import Settings

logger = logging.getLogger(__name__)

# Each entry: (config attribute name for the list name, fetcher callable)
_CURATED_FETCHERS: list[tuple[str, object]] = [
    (
        "SIMKL_LIST_NAME_KDRAMAS",
        lambda simkl, max, sort, year: simkl.fetch_trending_kdramas(max=max, sort=sort, year=year),
    ),
    (
        "SIMKL_LIST_NAME_KREALITY",
        lambda simkl, max, sort, year: simkl.fetch_trending_kreality(max=max, sort=sort, year=year),
    ),
    (
        "SIMKL_LIST_NAME_REALITY",
        lambda simkl, max, sort, year: simkl.fetch_trending_reality(max=max, sort=sort, year=year),
    ),
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
