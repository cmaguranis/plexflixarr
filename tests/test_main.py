from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.main import _convert_arr_payload, app

client = TestClient(app)


# --- _convert_arr_payload unit tests ---

def test_convert_radarr_download():
    req = _convert_arr_payload({"eventType": "Download", "movie": {"title": "Inception"}})
    assert req is not None
    assert req.media_type == "movie"
    assert req.title == "Inception"
    assert req.show_name is None


def test_convert_sonarr_download():
    req = _convert_arr_payload({"eventType": "Download", "series": {"title": "The Bear"}})
    assert req is not None
    assert req.media_type == "episode"
    assert req.title == "The Bear"
    assert req.show_name == "The Bear"


def test_convert_non_download_returns_none():
    assert _convert_arr_payload({"eventType": "Grab", "movie": {"title": "X"}}) is None


def test_convert_missing_movie_and_series_returns_none():
    assert _convert_arr_payload({"eventType": "Download"}) is None


# --- /discover/arr/cleanup endpoint tests ---

def test_arr_cleanup_radarr():
    with patch("src.main.cleanup.run") as mock_run:
        resp = client.post(
            "/discover/arr/cleanup",
            json={"eventType": "Download", "movie": {"title": "Inception"}},
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "started"
    assert resp.json()["media_type"] == "movie"


def test_arr_cleanup_sonarr():
    with patch("src.main.cleanup.run") as mock_run:
        resp = client.post(
            "/discover/arr/cleanup",
            json={"eventType": "Download", "series": {"title": "The Bear"}},
        )
    assert resp.status_code == 200
    assert resp.json()["media_type"] == "episode"


def test_arr_cleanup_test_event():
    resp = client.post("/discover/arr/cleanup", json={"eventType": "Test"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_arr_cleanup_ignores_grab_event():
    resp = client.post(
        "/discover/arr/cleanup",
        json={"eventType": "Grab", "movie": {"title": "X"}},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ignored"
