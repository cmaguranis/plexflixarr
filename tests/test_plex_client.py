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
    section.refreshing = False  # initial state after update()
    type(section).refreshing = property(lambda self, _calls=iter([True, True, False]): next(_calls, False))
    client = PlexClient(config)
    client.refresh_and_wait("Discover Movies")


def test_search_calls_section_search(config, mock_plex_server):
    client = PlexClient(config)
    client.search("Discover Movies", "Inception", "movie")
    mock_plex_server.library.section.return_value.search.assert_called_once_with(title="Inception", libtype="movie")


def test_refresh_and_wait_times_out(config, mock_plex_server):
    section = mock_plex_server.library.section.return_value
    type(section).refreshing = property(lambda self: True)  # never finishes
    client = PlexClient(config)
    client.refresh_and_wait("Discover Movies", max_wait=0)  # should break immediately
