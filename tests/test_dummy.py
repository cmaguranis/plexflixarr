from unittest.mock import patch

import pytest

from src.dummy import create_dummy, delete_dummy, ensure_template, sanitize_filename


def test_sanitize_filename_strips_invalid_chars():
    assert sanitize_filename('The: "Show" <2024>') == "The Show 2024"


def test_sanitize_filename_strips_slashes():
    assert "/" not in sanitize_filename("AC/DC (2024)")


def test_ensure_template_skips_if_exists(tmp_path):
    template = tmp_path / "dummy.mkv"
    template.write_bytes(b"fake")
    with patch("src.dummy.subprocess.run") as mock_run:
        ensure_template(template)
        mock_run.assert_not_called()


def test_ensure_template_runs_ffmpeg(tmp_path):
    template = tmp_path / "dummy.mkv"
    with patch("src.dummy.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        ensure_template(template)
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "ffmpeg" in cmd
        assert str(template) in cmd


def test_ensure_template_raises_on_ffmpeg_failure(tmp_path):
    template = tmp_path / "dummy.mkv"
    with patch("src.dummy.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = "ffmpeg error"
        with pytest.raises(RuntimeError, match="ffmpeg failed"):
            ensure_template(template)


def test_create_dummy_movie(config, tmp_path):
    config.TEMPLATE_FILE.write_bytes(b"fake")
    result = create_dummy("Inception", "2010", "movie", config)
    assert result is not None
    assert (result / "Inception (2010).mkv").exists()


def test_create_dummy_show(config):
    config.TEMPLATE_FILE.write_bytes(b"fake")
    result = create_dummy("The Bear", "2022", "tv", config)
    assert result is not None
    assert (result / "Season 01" / "The Bear (2022) - S01E01.mkv").exists()


def test_create_dummy_skips_unknown_year(config):
    assert create_dummy("No Year Show", None, "tv", config) is None
    assert create_dummy("No Year Show", "Unknown", "tv", config) is None


def test_create_dummy_skips_if_real_exists(config):
    folder = config.REAL_MOVIES_PATH / "Inception (2010)"
    folder.mkdir(parents=True)
    assert create_dummy("Inception", "2010", "movie", config) is None


def test_create_dummy_skips_if_discover_exists(config):
    config.TEMPLATE_FILE.write_bytes(b"fake")
    create_dummy("Inception", "2010", "movie", config)
    # Second call should be skipped
    assert create_dummy("Inception", "2010", "movie", config) is None


def test_delete_dummy(tmp_path):
    folder = tmp_path / "Some Movie (2024)"
    folder.mkdir()
    (folder / "file.mkv").write_bytes(b"x")
    delete_dummy(folder)
    assert not folder.exists()


def test_delete_dummy_noop_if_missing(tmp_path):
    delete_dummy(tmp_path / "nonexistent")  # should not raise
