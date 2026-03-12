from pathlib import Path
from unittest.mock import MagicMock, patch

from src.jobs.cleanup import run


def _make_dummy_item(folder: Path) -> MagicMock:
    item = MagicMock()
    item.locations = [str(folder)]
    return item


def test_run_deletes_dummy_and_empties_trash(config, mock_plex_server, tmp_path):
    dummy_folder = tmp_path / "Some Show (2024)"
    dummy_folder.mkdir()
    (dummy_folder / "dummy.mkv").write_bytes(b"x")

    mock_plex_server.library.section.return_value.search.return_value = [
        _make_dummy_item(dummy_folder)
    ]

    with patch("src.jobs.cleanup.delete_dummy") as mock_del, \
         patch("src.clients.plex_client.time.sleep"):
        run("show", "Some Show", config)
        mock_del.assert_called_once_with(dummy_folder)

    mock_plex_server.library.section.return_value.emptyTrash.assert_called()


def test_run_noop_when_no_dummy_found(config, mock_plex_server):
    mock_plex_server.library.section.return_value.search.return_value = []
    with patch("src.jobs.cleanup.delete_dummy") as mock_del:
        run("show", "Missing Show", config)
        mock_del.assert_not_called()


def test_run_logs_error_for_unknown_media_type(config, mock_plex_server):
    with patch("src.jobs.cleanup.delete_dummy") as mock_del:
        run("anime", "Some Title", config)  # unknown type
        mock_del.assert_not_called()
