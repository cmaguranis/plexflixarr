import logging
import sys
from pathlib import Path

from src.clients.plex_client import PlexClient
from src.config import Settings
from src.dummy import delete_dummy

logger = logging.getLogger(__name__)

_DISCOVER_LIBS = {
    "show": "Discover Shows",
    "movie": "Discover Movies",
}


def run(media_type: str, title: str, config: Settings | None = None) -> None:
    """
    Remove the dummy placeholder for a title that has been acquired as real media.

    Called by Tautulli's Script Notification Agent when a real file is added to
    the main Plex library. Arguments:
        media_type: 'show' or 'movie'
        title:      exact title as reported by Tautulli
    """
    config = config or Settings()

    lib_name = _DISCOVER_LIBS.get(media_type)
    if not lib_name:
        logger.error("Unknown media_type '%s' — expected 'show' or 'movie'.", media_type)
        return

    plex = PlexClient(config)
    results = plex.search(lib_name, title, media_type)

    if not results:
        logger.info("No dummy found for '%s' in %s — nothing to clean up.", title, lib_name)
        return

    dummy = results[0]
    folder = Path(dummy.locations[0])
    logger.info("Cleaning up dummy for '%s' at %s", title, folder)

    delete_dummy(folder)
    plex.refresh_and_wait(lib_name)
    plex.empty_trash(lib_name)

    logger.info("Cleanup complete for '%s'.", title)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if len(sys.argv) < 3:
        print("Usage: cleanup <media_type> <title>", file=sys.stderr)
        sys.exit(1)

    run(media_type=sys.argv[1], title=sys.argv[2])
