import logging
import time

from plexapi.server import PlexServer

from src.config import Settings

logger = logging.getLogger(__name__)

_POLL_INTERVAL = 10  # seconds between scan-completion polls


def _plex_libtype(media_type: str) -> str:
    """Normalise TMDB/internal media_type to PlexAPI libtype ('movie' or 'show')."""
    return "show" if media_type in ("tv", "show", "shows") else "movie"


class PlexClient:
    def __init__(self, config: Settings) -> None:
        self._server = PlexServer(config.PLEX_URL, config.PLEX_TOKEN)

    def get_section(self, name: str):
        return self._server.library.section(name)

    def refresh_and_wait(self, *section_names: str) -> None:
        """Trigger a library scan on each section and block until all finish."""
        sections = [self.get_section(n) for n in section_names]
        for section in sections:
            section.update()
            logger.info("Scan started for library: %s", section.title)

        while any(self._server.library.section(s.title).refreshing for s in sections):
            logger.info("Waiting for Plex scan to complete...")
            time.sleep(_POLL_INTERVAL)

        logger.info("All library scans complete.")

    def exists_in_any(self, section_names: list[str], title: str, libtype: str) -> bool:
        """Return True if a title exists in any of the given library sections."""
        plex_type = _plex_libtype(libtype)
        for name in section_names:
            try:
                if self.get_section(name).search(title=title, libtype=plex_type):
                    return True
            except Exception as exc:
                logger.warning("Could not search Plex library '%s': %s", name, exc)
        return False

    def search(self, section_name: str, title: str, libtype: str) -> list:
        section = self.get_section(section_name)
        return section.search(title=title, libtype=_plex_libtype(libtype))

    def find_by_tmdb_id(self, section_name: str, tmdb_id: int, libtype: str) -> list:
        """Search a library section by TMDB ID via Plex guid matching."""
        section = self.get_section(section_name)
        return section.search(guid=f"tmdb://{tmdb_id}", libtype=_plex_libtype(libtype))

    def find_by_anilist_id(self, section_name: str, anilist_id: int, libtype: str) -> list:
        """Search a library section by AniList ID via Plex guid matching."""
        section = self.get_section(section_name)
        return section.search(guid=f"anilist://{anilist_id}", libtype=_plex_libtype(libtype))

    def add_labels(self, item, labels: list[str]) -> None:
        for label in labels:
            item.addLabel(label)
        logger.info("Labelled '%s' with %s", item.title, labels)

    def delete_item(self, item) -> None:
        item.delete()
        logger.info("Deleted Plex item: %s", item.title)

    def empty_trash(self, section_name: str) -> None:
        self.get_section(section_name).emptyTrash()
        logger.info("Emptied trash for library: %s", section_name)
