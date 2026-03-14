from unittest.mock import MagicMock, patch

import pytest

from src.clients.tmdb_client import TmdbItem
from src.clients.trakt_client import TraktItem
from src.jobs.ingestion import run

_REAL_LIBS = {"Movies", "Anime Movies", "TV Shows", "Anime TV"}


def _section_factory(found_item=None):
    """Return a side_effect for library.section that returns [] for real libs."""

    def _side_effect(name):
        section = MagicMock()
        section.refreshing = False
        hits = [found_item] if found_item else []
        section.search.return_value = [] if name in _REAL_LIBS else hits
        return section

    return _side_effect


@pytest.fixture(autouse=True)
def _disable_schedule(mocker):
    """Always enable the schedule so ingestion runs in tests."""
    mocker.patch("src.jobs.ingestion.Schedule.is_enabled", return_value=True)


@pytest.fixture(autouse=True)
def _mock_ensure_template(mocker):
    mocker.patch("src.jobs.ingestion.ensure_template")


@pytest.fixture(autouse=True)
def _mock_anilist(mocker):
    mocker.patch("src.jobs.ingestion.AniListClient")
    mocker.patch("src.jobs.ingestion.resolve_tmdb_id", return_value=None)


@pytest.fixture(autouse=True)
def _mock_plex_sleep(mocker):
    mocker.patch("src.clients.plex_client.time.sleep")


def _tmdb_item(title="Test Movie", year="2024", media_type="movie", tmdb_id=1, vote_count=0, vote_average=0.0):
    return TmdbItem(
        title=title,
        year=year,
        media_type=media_type,
        tmdb_id=tmdb_id,
        labels=["Discover_Netflix"],
        vote_count=vote_count,
        vote_average=vote_average,
    )


def _trakt_item(title="Trakt Show", year="2023", media_type="show"):
    return TraktItem(title=title, year=year, media_type=media_type)


def test_run_creates_dummy_and_labels_plex(config, mock_plex_server):
    config.TEMPLATE_FILE.write_bytes(b"fake")

    with (
        patch("src.jobs.ingestion.TmdbClient") as MockTmdb,
        patch("src.jobs.ingestion.TraktClient") as MockTrakt,
    ):
        MockTmdb.return_value.fetch_streaming.return_value = [_tmdb_item(vote_count=500, vote_average=7.5)]
        MockTrakt.return_value.fetch_recommendations.return_value = []

        found = MagicMock()
        mock_plex_server.library.section.side_effect = _section_factory(found)

        run(config)

    # Dummy file should have been created
    movies = list(config.DISCOVER_MOVIES_PATH.rglob("*.mkv"))
    assert len(movies) == 1


def test_run_skips_items_failing_quality_gate(config, mock_plex_server):
    config.TEMPLATE_FILE.write_bytes(b"fake")

    with (
        patch("src.jobs.ingestion.TmdbClient") as MockTmdb,
        patch("src.jobs.ingestion.TraktClient") as MockTrakt,
    ):
        # Low score — fails quality gate
        MockTmdb.return_value.fetch_streaming.return_value = [_tmdb_item(vote_count=500, vote_average=3.0)]
        MockTrakt.return_value.fetch_recommendations.return_value = []

        run(config)

    assert list(config.DISCOVER_MOVIES_PATH.rglob("*.mkv")) == []


def test_run_trakt_items_bypass_quality_gate(config, mock_plex_server):
    config.TEMPLATE_FILE.write_bytes(b"fake")

    with (
        patch("src.jobs.ingestion.TmdbClient") as MockTmdb,
        patch("src.jobs.ingestion.TraktClient") as MockTrakt,
    ):
        MockTmdb.return_value.fetch_streaming.return_value = []
        MockTrakt.return_value.fetch_recommendations.return_value = [_trakt_item()]

        found = MagicMock()
        mock_plex_server.library.section.side_effect = _section_factory(found)

        run(config)

    # Show dummy should still be created (Trakt items have no vote data, bypass quality gate)
    shows = list(config.DISCOVER_SHOWS_PATH.rglob("*.mkv"))
    assert len(shows) == 1


def test_run_exits_early_when_schedule_disabled(config, mocker):
    mocker.patch("src.jobs.ingestion.Schedule.is_enabled", return_value=False)
    with patch("src.jobs.ingestion.TmdbClient") as MockTmdb:
        run(config)
        MockTmdb.assert_not_called()
