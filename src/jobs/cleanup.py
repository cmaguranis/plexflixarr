import logging

from src.clients.plex_client import PlexClient
from src.config import Settings
from src.dummy import delete_dummy, item_folder

logger = logging.getLogger(__name__)

_DISCOVER_LIBS = {
    "episode": "Discover Shows",
    "season": "Discover Shows",
    "movie": "Discover Movies",
}


def run(media_type: str, title: str, show_name: str | None = None, config: Settings | None = None) -> None:
    """Remove the dummy placeholder for a title that has been acquired as real media."""
    config = config or Settings()

    lib_name = _DISCOVER_LIBS.get(media_type)
    if not lib_name:
        logger.error("Unknown media_type '%s' — expected 'episode', 'season', or 'movie'.", media_type)
        return

    lookup_title = show_name if media_type in ("episode", "season") else title

    plex = PlexClient(config)
    results = plex.search(lib_name, lookup_title, media_type)

    if not results:
        logger.info("No dummy found for '%s' in %s — nothing to clean up.", lookup_title, lib_name)
        return

    dummy = results[0]
    folder = item_folder(dummy, media_type, config)
    logger.info("Cleaning up dummy for '%s' at %s", lookup_title, folder)

    delete_dummy(folder)
    plex.refresh_and_wait(lib_name)
    plex.empty_trash(lib_name)

    logger.info("Cleanup complete for '%s'.", lookup_title)
