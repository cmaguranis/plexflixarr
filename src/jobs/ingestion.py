import logging
import time

from src.clients.mdblist_client import MdblistClient
from src.clients.plex_client import PlexClient
from src.clients.tmdb_client import TmdbClient, TmdbItem
from src.clients.trakt_client import TraktClient, TraktItem
from src.config import Settings
from src.dummy import create_dummy, ensure_template
from src.jobs.schedule import Schedule

logger = logging.getLogger(__name__)

_MDBLIST_RATE_DELAY = 1  # seconds between MDBList lookup calls (free tier: 1,000/day)
_INGEST_SCHEDULE_PATH = "scripts/ingest_schedule.json"
_DISCOVER_MOVIES_LIB = "Discover Movies"
_DISCOVER_SHOWS_LIB = "Discover Shows"


def _lib_and_type(media_type: str) -> tuple[str, str]:
    if media_type in ("movie", "movies"):
        return _DISCOVER_MOVIES_LIB, "movie"
    return _DISCOVER_SHOWS_LIB, "show"


def run(config: Settings | None = None) -> None:
    config = config or Settings()

    sched = Schedule(_INGEST_SCHEDULE_PATH)
    if not sched.is_enabled():
        logger.info("Ingestion schedule is disabled — exiting.")
        return

    ensure_template(config.TEMPLATE_FILE)

    items_to_tag: list[TmdbItem | TraktItem] = []
    mdblist = MdblistClient(config)

    # ── TMDB: trending content per streaming provider ─────────────────────────
    logger.info("Fetching TMDB streaming content...")
    for item in TmdbClient(config).fetch_streaming(config.PAGES_PER_PROVIDER):
        if not mdblist.passes_quality_check(item.tmdb_id, item.media_type):
            logger.debug("Rejected (quality): %s", item.title)
            continue
        time.sleep(_MDBLIST_RATE_DELAY)
        if create_dummy(item.title, item.year, item.media_type, config):
            items_to_tag.append(item)

    # ── Trakt: personalised Couchmoney recommendations ────────────────────────
    logger.info("Fetching Trakt recommendations...")
    for item in TraktClient(config).fetch_recommendations():
        # Trakt recs bypass MDBList — already personalised, no need to filter
        item_with_labels = _TraktItemWithLabels(item, ["Discover_Recs", "Discover_All"])
        if create_dummy(item.title, item.year, item.media_type, config):
            items_to_tag.append(item_with_labels)

    if not items_to_tag:
        logger.info("No new items to tag.")
        return

    # ── Plex: scan, wait, then apply labels ───────────────────────────────────
    logger.info("Triggering Plex library scans...")
    plex = PlexClient(config)
    plex.refresh_and_wait(_DISCOVER_MOVIES_LIB, _DISCOVER_SHOWS_LIB)

    logger.info("Applying Plex labels to %d items...", len(items_to_tag))
    for item in items_to_tag:
        lib_name, libtype = _lib_and_type(item.media_type)
        results = plex.search(lib_name, item.title, libtype)
        if results:
            plex.add_labels(results[0], item.labels)
        else:
            logger.warning("Plex item not found after scan: %s", item.title)

    logger.info("Ingestion complete.")


class _TraktItemWithLabels(TraktItem):
    """TraktItem extended with Plex labels for tagging."""

    def __init__(self, item: TraktItem, labels: list[str]) -> None:
        super().__init__(title=item.title, year=item.year, media_type=item.media_type)
        self.labels = labels


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run()
