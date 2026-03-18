import logging
import time
from collections import Counter
from collections.abc import Sequence

from plexapi.library import LibrarySection
from plexapi.server import PlexServer
from plexapi.video import Video

from src.clients.simkl_client.simkl_models import SimklItem
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

    def search(self, section_name: str, title: str, libtype: str) -> list[Video]:
        section = self.get_section(section_name)
        return section.search(title=title, libtype=_plex_libtype(libtype))

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

    def create_curated_collections(
        self,
        config: Settings,
        curated: dict[str, Sequence[SimklItem]],
        movie_lists: set[str] | None = None,
    ) -> None:
        """Upsert ordered Plex collections for each curated Simkl list.

        Existing collections are deleted and recreated so the trending rank order
        is always fresh. Movie collections search only the movies library;
        show collections search shows and real libraries.
        """
        movie_lists = movie_lists or set()
        show_sections = [config.DISCOVER_SHOWS_LIB, *config.REAL_LIBS]
        movie_sections = [config.DISCOVER_MOVIES_LIB, *config.REAL_LIBS]

        for collection_name, items in curated.items():
            is_movie = collection_name in movie_lists
            libtype = "movie" if is_movie else "show"
            sections = movie_sections if is_movie else show_sections

            item_list = list(items)
            logger.info(
                "Building curated collection '%s' (%s) from %d Simkl items.",
                collection_name, libtype, len(item_list),
            )

            found: list[tuple] = []  # (plex_item, section_name)
            for item in item_list:
                if item.ids.tmdb is None:
                    logger.info(
                        "  '%s' → skipped (no TMDB ID) ids=%s", item.title, item.ids.model_dump(exclude_none=True)
                    )
                    continue
                for section_name in sections:
                    try:
                        results = self.search(section_name, item.title, libtype)
                        if results:
                            matched = results[0]
                            logger.info(
                                "  '%s' (tmdb=%s) → matched '%s' in '%s' (ratingKey=%s)",
                                item.title,
                                item.ids.tmdb,
                                matched.title,
                                section_name,
                                matched.ratingKey,
                            )
                            found.append((matched, section_name))
                            break
                    except Exception:
                        continue
                else:
                    logger.info("  '%s' (tmdb=%s) → not found in any library", item.title, item.ids.tmdb)

            if not found:
                logger.warning("No Plex items found for curated collection '%s' — skipping.", collection_name)
                continue

            # All items must be in the same section for a Plex collection.
            preferred = config.DISCOVER_MOVIES_LIB if is_movie else config.DISCOVER_SHOWS_LIB
            section_counts = Counter(section for _, section in found)
            target_section = max(
                section_counts,
                key=lambda s: (section_counts[s], s == preferred),
            )
            rating_keys = [plex_item.ratingKey for plex_item, section in found if section == target_section]

            logger.info(
                "Creating collection '%s' in '%s' with %d/%d items.",
                collection_name,
                target_section,
                len(rating_keys),
                len(item_list),
            )
            self.delete_collection_if_exists(target_section, collection_name)
            self.create_custom_ordered_collection(collection_name, rating_keys)
            logger.info("Upserted curated collection '%s'.", collection_name)
