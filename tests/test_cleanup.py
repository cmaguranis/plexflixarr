from unittest.mock import MagicMock, patch

from src.jobs.cleanup import run


def _make_dummy_item(plex_path: str) -> MagicMock:
    item = MagicMock()
    item.locations = [plex_path]
    return item


def test_run_deletes_show_dummy(config, mock_plex_server):
    mock_plex_server.library.section.return_value.search.return_value = [
        _make_dummy_item("/discover_shows/Some Show (2024)")
    ]

    with (
        patch("src.jobs.cleanup.delete_dummy") as mock_del,
        patch("src.clients.plex_client.time.sleep"),
    ):
        run({"eventType": "Download", "series": {"title": "Some Show"}}, config=config)
        mock_del.assert_called_once_with(config.DISCOVER_SHOWS_PATH / "Some Show (2024)")

    mock_plex_server.library.section.return_value.emptyTrash.assert_called()


def test_run_deletes_movie_dummy(config, mock_plex_server):
    mock_plex_server.library.section.return_value.search.return_value = [
        _make_dummy_item("/discover_movies/Inception (2010)/Inception (2010).mkv")
    ]

    with (
        patch("src.jobs.cleanup.delete_dummy") as mock_del,
        patch("src.clients.plex_client.time.sleep"),
    ):
        run({"eventType": "Download", "movie": {"title": "Inception"}}, config=config)
        mock_del.assert_called_once_with(config.DISCOVER_MOVIES_PATH / "Inception (2010)")


def test_run_noop_when_no_dummy_found(config, mock_plex_server):
    mock_plex_server.library.section.return_value.search.return_value = []
    with patch("src.jobs.cleanup.delete_dummy") as mock_del:
        run({"eventType": "Download", "series": {"title": "Missing Show"}}, config=config)
        mock_del.assert_not_called()


def test_run_ignores_payload_without_media_key(config, mock_plex_server):
    with patch("src.jobs.cleanup.delete_dummy") as mock_del:
        run({"eventType": "Download"}, config=config)
        mock_del.assert_not_called()
