from unittest.mock import MagicMock, patch

import pytest

from src.clients.tmdb_client import TmdbItem
from src.clients.trakt_client import TraktItem
from src.jobs.ingestion import run


@pytest.fixture(autouse=True)
def _disable_schedule(mocker):
    """Always enable the schedule so ingestion runs in tests."""
    mocker.patch("src.jobs.ingestion.Schedule.is_enabled", return_value=True)


@pytest.fixture(autouse=True)
def _mock_ensure_template(mocker):
    mocker.patch("src.jobs.ingestion.ensure_template")


def _tmdb_item(title="Test Movie", year="2024", media_type="movie", tmdb_id=1):
    return TmdbItem(title=title, year=year, media_type=media_type, tmdb_id=tmdb_id,
                    labels=["Discover_Netflix", "Discover_All"])


def _trakt_item(title="Trakt Show", year="2023", media_type="show"):
    return TraktItem(title=title, year=year, media_type=media_type)


def test_run_creates_dummy_and_labels_plex(config, mock_plex_server):
    config.TEMPLATE_FILE.write_bytes(b"fake")

    with patch("src.jobs.ingestion.TmdbClient") as MockTmdb, \
         patch("src.jobs.ingestion.TraktClient") as MockTrakt, \
         patch("src.jobs.ingestion.MdblistClient") as MockMdb, \
         patch("src.jobs.ingestion.time.sleep"):

        MockTmdb.return_value.fetch_streaming.return_value = [_tmdb_item()]
        MockTrakt.return_value.fetch_recommendations.return_value = []
        MockMdb.return_value.passes_quality_check.return_value = True

        mock_plex_server.library.section.return_value.search.return_value = [MagicMock()]

        run(config)

    # Dummy file should have been created
    movies = list(config.DISCOVER_MOVIES_PATH.rglob("*.mkv"))
    assert len(movies) == 1


def test_run_skips_items_failing_mdblist(config, mock_plex_server):
    config.TEMPLATE_FILE.write_bytes(b"fake")

    with patch("src.jobs.ingestion.TmdbClient") as MockTmdb, \
         patch("src.jobs.ingestion.TraktClient") as MockTrakt, \
         patch("src.jobs.ingestion.MdblistClient") as MockMdb, \
         patch("src.jobs.ingestion.time.sleep"):

        MockTmdb.return_value.fetch_streaming.return_value = [_tmdb_item()]
        MockTrakt.return_value.fetch_recommendations.return_value = []
        MockMdb.return_value.passes_quality_check.return_value = False

        run(config)

    assert list(config.DISCOVER_MOVIES_PATH.rglob("*.mkv")) == []


def test_run_trakt_items_bypass_mdblist(config, mock_plex_server):
    config.TEMPLATE_FILE.write_bytes(b"fake")

    with patch("src.jobs.ingestion.TmdbClient") as MockTmdb, \
         patch("src.jobs.ingestion.TraktClient") as MockTrakt, \
         patch("src.jobs.ingestion.MdblistClient") as MockMdb, \
         patch("src.jobs.ingestion.time.sleep"):

        MockTmdb.return_value.fetch_streaming.return_value = []
        MockTrakt.return_value.fetch_recommendations.return_value = [_trakt_item()]
        MockMdb.return_value.passes_quality_check.return_value = False  # would reject

        mock_plex_server.library.section.return_value.search.return_value = [MagicMock()]

        run(config)

    # Show dummy should still be created (Trakt bypasses MDBList)
    shows = list(config.DISCOVER_SHOWS_PATH.rglob("*.mkv"))
    assert len(shows) == 1


def test_run_exits_early_when_schedule_disabled(config, mocker):
    mocker.patch("src.jobs.ingestion.Schedule.is_enabled", return_value=False)
    with patch("src.jobs.ingestion.TmdbClient") as MockTmdb:
        run(config)
        MockTmdb.assert_not_called()
