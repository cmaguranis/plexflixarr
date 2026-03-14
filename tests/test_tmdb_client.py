from unittest.mock import MagicMock, patch

from src.clients.tmdb_client import TmdbClient


def _mock_response(results: list[dict]) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {"results": results}
    return resp


def test_fetch_streaming_returns_tmdb_items(config):
    movie = {"id": 1, "title": "Test Movie", "release_date": "2024-01-01"}
    show = {"id": 2, "name": "Test Show", "first_air_date": "2024-02-01"}

    with (
        patch("src.clients.tmdb_client.requests.get") as mock_get,
        patch("src.clients.tmdb_client.time.sleep"),
    ):
        mock_get.side_effect = lambda url, **_: _mock_response([movie]) if "/movie" in url else _mock_response([show])
        client = TmdbClient(config)
        results = client.fetch_streaming(pages=1)

    assert any(r.title == "Test Movie" and r.media_type == "movie" for r in results)
    assert any(r.title == "Test Show" and r.media_type == "tv" for r in results)


def test_fetch_streaming_includes_tmdb_id(config):
    movie = {"id": 42, "title": "IDed Movie", "release_date": "2024-01-01"}
    with (
        patch("src.clients.tmdb_client.requests.get") as mock_get,
        patch("src.clients.tmdb_client.time.sleep"),
    ):
        mock_get.return_value = _mock_response([movie])
        results = TmdbClient(config).fetch_streaming(pages=1)

    movie_results = [r for r in results if r.media_type == "movie"]
    assert any(r.tmdb_id == 42 for r in movie_results)


def test_fetch_streaming_attaches_provider_label(config):
    movie = {"id": 1, "title": "Netflix Movie", "release_date": "2024-01-01"}
    with (
        patch("src.clients.tmdb_client.requests.get") as mock_get,
        patch("src.clients.tmdb_client.time.sleep"),
    ):
        mock_get.return_value = _mock_response([movie])
        results = TmdbClient(config).fetch_streaming(pages=1)

    netflix_results = [r for r in results if "Discover_Netflix" in r.labels]
    assert len(netflix_results) > 0


def test_fetch_streaming_handles_api_error(config):
    with (
        patch("src.clients.tmdb_client.requests.get") as mock_get,
        patch("src.clients.tmdb_client.time.sleep"),
    ):
        mock_get.side_effect = Exception("network error")
        results = TmdbClient(config).fetch_streaming(pages=1)
    assert results == []
