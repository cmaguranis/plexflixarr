from unittest.mock import MagicMock, patch

from src.clients.mdblist_client import MdblistClient


def _mock_response(ratings: list[dict], error: str | None = None) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    data = {"ratings": ratings}
    if error:
        data["error"] = error
    resp.json.return_value = data
    return resp


def test_passes_trakt_threshold(config):
    resp = _mock_response([{"source": "trakt", "value": 80}])
    with patch("src.clients.mdblist_client.requests.get", return_value=resp):
        assert MdblistClient(config).passes_quality_check(1, "movie") is True


def test_fails_trakt_below_threshold(config):
    resp = _mock_response([{"source": "trakt", "value": 50}])
    with patch("src.clients.mdblist_client.requests.get", return_value=resp):
        assert MdblistClient(config).passes_quality_check(1, "movie") is False


def test_passes_rt_threshold(config):
    resp = _mock_response([{"source": "tomatoes", "value": 75}])
    with patch("src.clients.mdblist_client.requests.get", return_value=resp):
        assert MdblistClient(config).passes_quality_check(1, "tv") is True


def test_fails_when_item_not_on_mdblist(config):
    resp = _mock_response([], error="Item not found")
    with patch("src.clients.mdblist_client.requests.get", return_value=resp):
        assert MdblistClient(config).passes_quality_check(999, "movie") is False


def test_fails_on_network_error(config):
    with patch("src.clients.mdblist_client.requests.get", side_effect=Exception("timeout")):
        assert MdblistClient(config).passes_quality_check(1, "movie") is False


def test_maps_tv_to_show_param(config):
    resp = _mock_response([{"source": "trakt", "value": 80}])
    with patch("src.clients.mdblist_client.requests.get", return_value=resp) as mock_get:
        MdblistClient(config).passes_quality_check(1, "tv")
        _, kwargs = mock_get.call_args
        assert kwargs["params"]["m"] == "show"
