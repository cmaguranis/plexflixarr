"""
Renders kometa-config/discovery_ui.yml from discovery_ui.template.yml.

Called at the end of each ingestion run so that newly discovered Couchmoney
themed lists automatically get a matching Smart Collection row in Plex.
"""

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from src.clients.trakt_client import TraktList

logger = logging.getLogger(__name__)

_KOMETA_CONFIG_DIR = Path("kometa-config")
_TEMPLATE_FILE = "discovery_ui.template.yml"
_OUTPUT_FILE = _KOMETA_CONFIG_DIR / "discovery_ui.yml"
_SORT_PREFIX_START = 30  # Static collections occupy 00–27


def generate(trakt_lists: list[TraktList]) -> None:
    """
    Render discovery_ui.template.yml → discovery_ui.yml.

    Each TraktList becomes one Smart Collection row at sort prefixes 30, 31, …
    Pass an empty list to render with no dynamic collections (safe default).
    """
    env = Environment(
        loader=FileSystemLoader(str(_KOMETA_CONFIG_DIR)),
        keep_trailing_newline=True,
    )
    template = env.get_template(_TEMPLATE_FILE)

    collections = [
        {
            "display_name": lst.display_name,
            "label": lst.label,
            "sort_prefix": str(_SORT_PREFIX_START + i).zfill(2),
        }
        for i, lst in enumerate(trakt_lists)
    ]

    rendered = template.render(couchmoney_collections=collections)
    _OUTPUT_FILE.write_text(rendered, encoding="utf-8")
    logger.info(
        "Regenerated %s with %d Couchmoney themed collection(s).",
        _OUTPUT_FILE,
        len(collections),
    )
