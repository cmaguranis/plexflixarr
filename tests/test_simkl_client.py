from unittest.mock import MagicMock

import pytest

from src.clients.simkl_client.simkl_client import SimklClient
from src.clients.simkl_client.simkl_models import TvSort
from src.config import Settings


@pytest.fixture
def simkl_config(config: Settings) -> Settings:
    return Settings(**{**config.model_dump(), "SIMKL_CLIENT_ID": "test-simkl-id"})


@pytest.fixture
def client(simkl_config: Settings) -> SimklClient:
    return SimklClient(simkl_config)


def _mock_fetch(client: SimklClient, mocker) -> MagicMock:
    """Patch _fetch_genres_page to return empty list and capture calls."""
    return mocker.patch.object(client, "_fetch_genres_page", return_value=[])


class TestFetchTrendingKdramas:
    def test_default_sort(self, client, mocker):
        mock = _mock_fetch(client, mocker)
        client.fetch_trending_kdramas(max=1)
        url_arg = mock.call_args[0][0]
        assert url_arg == "/tv/genres/all-types/kr/this-year/popular-this-week"

    def test_custom_sort_today(self, client, mocker):
        mock = _mock_fetch(client, mocker)
        client.fetch_trending_kdramas(max=1, sort=TvSort.POPULAR_TODAY)
        url_arg = mock.call_args[0][0]
        assert url_arg == "/tv/genres/all-types/kr/this-year/popular-today"

    def test_custom_sort_month(self, client, mocker):
        mock = _mock_fetch(client, mocker)
        client.fetch_trending_kdramas(max=1, sort=TvSort.POPULAR_THIS_MONTH)
        url_arg = mock.call_args[0][0]
        assert url_arg == "/tv/genres/all-types/kr/this-year/popular-this-month"


class TestFetchTrendingKreality:
    def test_default_sort(self, client, mocker):
        mock = _mock_fetch(client, mocker)
        client.fetch_trending_kreality(max=1)
        url_arg = mock.call_args[0][0]
        assert url_arg == "/tv/genres/reality/all-types/kr/this-year/popular-this-week"

    def test_custom_sort_today(self, client, mocker):
        mock = _mock_fetch(client, mocker)
        client.fetch_trending_kreality(max=1, sort=TvSort.POPULAR_TODAY)
        url_arg = mock.call_args[0][0]
        assert url_arg == "/tv/genres/reality/all-types/kr/this-year/popular-today"


class TestFetchTrendingReality:
    def test_default_sort(self, client, mocker):
        mock = _mock_fetch(client, mocker)
        client.fetch_trending_reality(max=1)
        url_arg = mock.call_args[0][0]
        assert url_arg == "/tv/genres/entertainment/this-year/popular-this-week"

    def test_no_country_filter(self, client, mocker):
        mock = _mock_fetch(client, mocker)
        client.fetch_trending_reality(max=1)
        url_arg = mock.call_args[0][0]
        assert "/kr/" not in url_arg

    def test_custom_sort_month(self, client, mocker):
        mock = _mock_fetch(client, mocker)
        client.fetch_trending_reality(max=1, sort=TvSort.POPULAR_THIS_MONTH)
        url_arg = mock.call_args[0][0]
        assert url_arg == "/tv/genres/entertainment/this-year/popular-this-month"
