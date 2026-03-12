from unittest.mock import MagicMock, patch

from src.clients.trakt_client import TraktClient


def _mock_response(items: list[dict]) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = items
    return resp


def test_fetch_recommendations_returns_items(config):
    payload = [
        {"type": "movie", "movie": {"title": "Rec Movie", "year": 2023}},
        {"type": "show", "show": {"title": "Rec Show", "year": 2022}},
    ]
    with (
        patch("src.clients.trakt_client.requests.get", return_value=_mock_response(payload)),
        patch("src.clients.trakt_client.time.sleep"),
    ):
        results = TraktClient(config).fetch_recommendations()

    titles = [r.title for r in results]
    assert "Rec Movie" in titles
    assert "Rec Show" in titles


def test_fetch_recommendations_handles_missing_year(config):
    payload = [{"type": "movie", "movie": {"title": "No Year Movie"}}]
    with (
        patch("src.clients.trakt_client.requests.get", return_value=_mock_response(payload)),
        patch("src.clients.trakt_client.time.sleep"),
    ):
        results = TraktClient(config).fetch_recommendations()
    assert results[0].year is None


def test_fetch_recommendations_handles_api_error(config):
    with (
        patch("src.clients.trakt_client.requests.get", side_effect=Exception("error")),
        patch("src.clients.trakt_client.time.sleep"),
    ):
        results = TraktClient(config).fetch_recommendations()
    assert results == []
