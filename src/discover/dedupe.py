import logging

from src.clients.plex_client import PlexClient
from src.config import Settings
from src.dummy import delete_dummy, item_folder
from src.ingestion.shared import _base_title

logger = logging.getLogger(__name__)

_DISCOVER_LIBS: list[tuple[str, str]] = [
    # (discover_lib, libtype)
    ("Discover Movies", "movie"),
    ("Discover Shows", "show"),
]


def run(config: Settings | None = None) -> dict:
    """
    Remove dummy placeholders for any titles that now exist in the real Plex libraries.

    Returns a summary dict with counts of removed items per library.
    """
    config = config or Settings()
    plex = PlexClient(config)

    removed: dict[str, int] = {}

    for discover_lib, libtype in _DISCOVER_LIBS:
        count = 0
        try:
            section = plex.get_section(discover_lib)
        except Exception as exc:
            logger.warning("Could not access discover library '%s': %s", discover_lib, exc)
            continue

        for item in section.all():
            base = _base_title(item.title)
            if plex.exists_in_any(config.REAL_LIBS, base, libtype):
                folder = item_folder(item, libtype, config)
                logger.info("Deduping '%s' (found in real library) — removing %s", item.title, folder)
                delete_dummy(folder)
                count += 1

        if count:
            plex.refresh_and_wait(discover_lib)
            plex.empty_trash(discover_lib)

        removed[discover_lib] = count
        logger.info("Dedupe complete for '%s': %d item(s) removed.", discover_lib, count)

    return removed
