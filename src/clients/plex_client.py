import logging
import time

from plexapi.library import LibrarySection
from plexapi.server import PlexServer
from plexapi.video import Video

from src.config import Settings

logger = logging.getLogger(__name__)

_POLL_INTERVAL = 10  # seconds between scan-completion polls


def _plex_libtype(media_type: str) -> str:
    """Normalise TMDB/internal media_type to PlexAPI libtype ('movie' or 'show')."""
    return "show" if media_type in ("tv", "show", "shows") else "movie"


class PlexClient:
    def __init__(self, config: Settings, retries: int = 6, retry_delay: int = 10) -> None:
        token = config.PLEX_TOKEN or None
        last_exc: Exception | None = None
        for attempt in range(retries):
            try:
                self._server = PlexServer(config.PLEX_URL, token)
                return
            except Exception as exc:
                last_exc = exc
                if attempt < retries - 1:
                    logger.warning(
                        "Plex connection failed (attempt %d/%d): %s — retrying in %ds",
                        attempt + 1,
                        retries,
                        exc,
                        retry_delay,
                    )
                    time.sleep(retry_delay)
        raise RuntimeError(f"Could not connect to Plex after {retries} attempts") from last_exc

    def get_section(self, name: str) -> LibrarySection:
        return self._server.library.section(name)

    def ensure_library(self, name: str, lib_type: str, location: str) -> None:
        """Create a Plex library section if it doesn't already exist."""
        try:
            self._server.library.section(name)
            return  # already exists
        except Exception:
            pass
        type_map = {
            "movie": ("tv.plex.agents.movie", "Plex Movie"),
            "show": ("tv.plex.agents.series", "Plex TV Series"),
        }
        agent, scanner = type_map[lib_type]
        self._server.library.add(name=name, type=lib_type, agent=agent, scanner=scanner, location=location)
        logger.info("Created Plex library '%s' at %s", name, location)

    def refresh_and_wait(self, *section_names: str, max_wait: int = 300, delay: int = 30) -> None:
        """Trigger a library scan on each section and block until all finish."""
        sections = [self.get_section(n) for n in section_names]
        for section in sections:
            section.update()
            logger.info("Scan started for library: %s", section.title)

        # Plex sets `refreshing` asynchronously — give it a moment before polling.
        time.sleep(delay)

        elapsed = 3
        while any(self._server.library.section(s.title).refreshing for s in sections):
            if elapsed >= max_wait:
                logger.warning("Plex scan did not finish within %ds — proceeding anyway.", max_wait)
                break
            logger.info("Waiting for Plex scan to complete...")
            time.sleep(_POLL_INTERVAL)
            elapsed += _POLL_INTERVAL

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

    def search(self, section_name: str, title: str, libtype: str) -> list[Video]:
        section = self.get_section(section_name)
        return section.search(title=title, libtype=_plex_libtype(libtype))

    def find_by_tmdb_id(self, section_name: str, tmdb_id: int, libtype: str) -> list[Video]:
        """Search a library section by TMDB ID via Plex guid matching."""
        section = self.get_section(section_name)
        return section.search(guid=f"tmdb://{tmdb_id}", libtype=_plex_libtype(libtype))

    def find_by_anilist_id(self, section_name: str, anilist_id: int, libtype: str) -> list[Video]:
        """Search a library section by AniList ID via Plex guid matching."""
        section = self.get_section(section_name)
        return section.search(guid=f"anilist://{anilist_id}", libtype=_plex_libtype(libtype))

    def query_search(self, section_name: str, query: str, libtype: str) -> list[Video]:
        """Fuzzy hub search scoped to a single library section."""
        section = self.get_section(section_name)
        plex_type = _plex_libtype(libtype)
        results = self._server.search(query, mediatype=plex_type, limit=5)
        return [r for r in results if getattr(r, "librarySectionID", None) == int(section.key)]

    def add_labels(self, item: Video, labels: list[str]) -> None:
        for label in labels:
            item.addLabel(label)
        logger.info("Labelled '%s' with %s", item.title, labels)

    def delete_item(self, item: Video) -> None:
        item.delete()
        logger.info("Deleted Plex item: %s", item.title)

    def empty_trash(self, section_name: str) -> None:
        self.get_section(section_name).emptyTrash()
        logger.info("Emptied trash for library: %s", section_name)

    def create_custom_ordered_collection(self, collection_name: str, items: list[int]) -> None:
        """Create a collection with items in a fixed custom sort order.

        Args:
            collection_name: Title of the Plex collection to create.
            items: Plex rating keys (str) of the items to include, in the
                desired display order. The section is inferred from the first item.
        """
        if not items:
            return
        plex_items = [self._server.fetchItem(key) for key in items]
        section = plex_items[0].section()
        collection = section.createCollection(collection_name, items=plex_items)
        collection.sortUpdate("custom")
        # moveItem enforces explicit rank order; each item is moved after the previous one
        collection.moveItem(plex_items[0])
        for i in range(1, len(plex_items)):
            collection.moveItem(plex_items[i], after=plex_items[i - 1])
        collection.visibility().updateVisibility(recommended=True, home=True, shared=True)
        logger.info("Created collection '%s' with %d items", collection_name, len(plex_items))

    def delete_collection_if_exists(self, section_name: str, collection_name: str) -> None:
        try:
            self.get_section(section_name).collection(collection_name).delete()
            logger.info("Deleted collection '%s'", collection_name)
        except Exception:
            pass

    def clear_collection(self, section_name: str, collection_name: str) -> None:
        """Remove all items from an existing collection.

        Args:
            section_name: Library section that owns the collection.
            collection_name: Title of the collection to empty.
        """
        section = self.get_section(section_name)
        collection = section.collection(collection_name)
        items = collection.items()
        if items:
            collection.removeItems(items)
        logger.info("Cleared collection '%s'", collection_name)
