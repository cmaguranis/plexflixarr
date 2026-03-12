from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.config import Settings


@pytest.fixture
def config(tmp_path: Path) -> Settings:
    """Minimal Settings instance wired to a temp directory."""
    return Settings(
        TMDB_API_KEY="test-tmdb-key",
        TRAKT_CLIENT_ID="test-trakt-id",
        MDBLIST_API_KEY="test-mdblist-key",
        PLEX_URL="http://localhost:32400",
        PLEX_TOKEN="test-plex-token",
        TEMPLATE_FILE=tmp_path / "dummy.mkv",
        DISCOVER_MOVIES_PATH=tmp_path / "discover_movies",
        DISCOVER_SHOWS_PATH=tmp_path / "discover_shows",
        PAGES_PER_PROVIDER=1,
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
