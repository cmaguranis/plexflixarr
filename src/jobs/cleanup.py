import logging
import threading
from typing import Any

from src.clients.plex_client import PlexClient
from src.config import Settings
from src.dummy import delete_dummy, item_folder

logger = logging.getLogger(__name__)

_SERIES_LIB = "Discover Shows"
_MOVIE_LIB = "Discover Movies"

_TRASH_DEBOUNCE_SECS = 10
_trash_timers: dict[str, threading.Timer] = {}
_trash_lock = threading.Lock()


def _schedule_empty_trash(lib_name: str, config: Settings) -> None:
    """Debounce empty_trash per library — resets the timer on each call."""
    with _trash_lock:
        existing = _trash_timers.get(lib_name)
        if existing:
            existing.cancel()

        def _flush() -> None:
            with _trash_lock:
                _trash_timers.pop(lib_name, None)
            logger.info("Emptying trash for %s", lib_name)
            PlexClient(config).empty_trash(lib_name)

        timer = threading.Timer(_TRASH_DEBOUNCE_SECS, _flush)
        _trash_timers[lib_name] = timer
        timer.start()


def run(payload: dict[str, Any], config: Settings | None = None) -> None:
    """Remove the dummy placeholder for a title based on an arr webhook payload."""
    config = config or Settings()

    if "movie" in payload:
        media_type = "movie"
        title = payload["movie"].get("title", "")
        lib_name = _MOVIE_LIB
    elif "series" in payload:
        media_type = "episode"
        title = payload["series"].get("title", "")
        lib_name = _SERIES_LIB
    else:
        logger.warning("Cleanup payload has no 'movie' or 'series' key — ignoring.")
        return

    plex = PlexClient(config)
    results = plex.search(lib_name, title, media_type)

    if not results:
        logger.info("No dummy found for '%s' in %s — nothing to clean up.", title, lib_name)
        return

    dummy = results[0]
    folder = item_folder(dummy, media_type, config)
    logger.info("Cleaning up dummy for '%s' at %s", title, folder)

    delete_dummy(folder)
    plex.refresh_and_wait(lib_name)
    _schedule_empty_trash(lib_name, config)

    logger.info("Cleanup complete for '%s'.", title)
