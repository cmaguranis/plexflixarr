from unittest.mock import MagicMock, call

import pytest

from src.clients.plex_client import PlexClient


@pytest.fixture(autouse=True)
def _mock_sleep(mocker):
    mocker.patch("src.clients.plex_client.time.sleep")


def test_refresh_and_wait_triggers_update(config, mock_plex_server):
    client = PlexClient(config)
    client.refresh_and_wait("Discover Movies")
    mock_plex_server.library.section.return_value.update.assert_called()


def test_refresh_and_wait_polls_until_done(config, mock_plex_server):
    section = mock_plex_server.library.section.return_value
    # First call: still refreshing; second call: done
    section.refreshing = False  # initial state after update()
    # Simulate the server returning refreshing=True then False
    type(section).refreshing = property(lambda self, _calls=iter([True, True, False]): next(_calls, False))
    client = PlexClient(config)
    client.refresh_and_wait("Discover Movies")


def test_search_calls_section_search(config, mock_plex_server):
    client = PlexClient(config)
    client.search("Discover Movies", "Inception", "movie")
    mock_plex_server.library.section.return_value.search.assert_called_once_with(title="Inception", libtype="movie")


def test_add_labels_calls_addLabel_per_label(config, mock_plex_server):
    client = PlexClient(config)
    item = MagicMock()
    client.add_labels(item, ["Discover_Netflix", "Discover_All"])
    assert item.addLabel.call_count == 2
    item.addLabel.assert_has_calls([call("Discover_Netflix"), call("Discover_All")])


def test_empty_trash(config, mock_plex_server):
    client = PlexClient(config)
    client.empty_trash("Discover Movies")
    mock_plex_server.library.section.return_value.emptyTrash.assert_called_once()


def test_refresh_and_wait_times_out(config, mock_plex_server):
    section = mock_plex_server.library.section.return_value
    type(section).refreshing = property(lambda self: True)  # never finishes
    client = PlexClient(config)
    client.refresh_and_wait("Discover Movies", max_wait=0)  # should break immediately
