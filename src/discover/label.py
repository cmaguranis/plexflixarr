import logging

from src.clients.plex_client import PlexClient
from src.config import Settings
from src.ingestion.ingestion import fetch_media
from src.ingestion.shared import label_discover_items

logger = logging.getLogger(__name__)


def run(config: Settings | None = None) -> None:
    """
    Apply missing Discover_* labels to unlabelled items in the Discover libraries.

    Re-fetches source data to determine correct labels, then applies any that are
    missing from items already present in the Discover libraries.
    """
    config = config or Settings()
    items = fetch_media(config)
    plex = PlexClient(config)
    label_discover_items(items, plex, config)
    logger.info("Label run complete.")
