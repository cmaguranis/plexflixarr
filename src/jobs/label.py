import logging

from src.clients.plex_client import PlexClient
from src.config import Settings
from src.jobs.ingestion import apply_labels, fetch_media

logger = logging.getLogger(__name__)


def run(config: Settings | None = None) -> None:
    """
    Apply missing Discover_* labels to unlabelled items in the Discover libraries.

    Re-fetches source data to determine correct labels, then applies any that are
    missing from items already present in the Discover libraries.
    """
    config = config or Settings()
    items, _ = fetch_media(config)
    plex = PlexClient(config)
    apply_labels(items, plex)
    logger.info("Label run complete.")
