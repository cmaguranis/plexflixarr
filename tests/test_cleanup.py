from unittest.mock import MagicMock, patch

from src.jobs.cleanup import run


def _make_dummy_item(plex_path: str) -> MagicMock:
    item = MagicMock()
    item.locations = [plex_path]
    return item


def test_run_deletes_dummy_and_empties_trash(config, mock_plex_server):
    # Simulate Plex reporting a show folder path (Plex-internal root differs from OS root)
    mock_plex_server.library.section.return_value.search.return_value = [
        _make_dummy_item("/discover_shows/Some Show (2024)")
    ]

    with (
        patch("src.jobs.cleanup.delete_dummy") as mock_del,
        patch("src.clients.plex_client.time.sleep"),
    ):
        run("episode", "Some Show", config=config)
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
        run("movie", "Inception", config=config)
        mock_del.assert_called_once_with(config.DISCOVER_MOVIES_PATH / "Inception (2010)")


def test_run_deletes_show_dummy_for_season(config, mock_plex_server):
    mock_plex_server.library.section.return_value.search.return_value = [
        _make_dummy_item("/discover_shows/The Bear (2022)")
    ]

    with (
        patch("src.jobs.cleanup.delete_dummy") as mock_del,
        patch("src.clients.plex_client.time.sleep"),
    ):
        run("season", "Season 1", show_name="The Bear", config=config)
        mock_del.assert_called_once_with(config.DISCOVER_SHOWS_PATH / "The Bear (2022)")


def test_run_noop_when_no_dummy_found(config, mock_plex_server):
    mock_plex_server.library.section.return_value.search.return_value = []
    with patch("src.jobs.cleanup.delete_dummy") as mock_del:
        run("episode", "Missing Show", config=config)
        mock_del.assert_not_called()


def test_run_logs_error_for_unknown_media_type(config, mock_plex_server):
    with patch("src.jobs.cleanup.delete_dummy") as mock_del:
        run("anime", "Some Title", config=config)  # unknown type
        mock_del.assert_not_called()
