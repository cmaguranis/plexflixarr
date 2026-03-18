from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.config import Settings


@pytest.fixture
def config(tmp_path: Path) -> Settings:
    """Minimal Settings instance wired to a temp directory."""
    return Settings(
        TMDB_API_KEY="test-tmdb-key",
        PLEX_URL="http://localhost:32400",
        PLEX_TOKEN="test-plex-token",
        SIMKL_LISTS_DB_FILE=tmp_path / "simkl_lists.db",
    )


@pytest.fixture
def mock_plex_server(mocker):
    """Mock PlexServer so tests never make real network calls."""
    mock = mocker.patch("src.clients.plex_client.PlexServer")
    server = MagicMock()
    mock.return_value = server
    # Default: no active scans
    server.library.section.return_value.refreshing = False
    return server
