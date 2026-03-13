from unittest.mock import patch

from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_arr_cleanup_radarr():
    with patch("src.main.cleanup.run"):
        resp = client.post(
            "/discover/arr/cleanup",
            json={"eventType": "Download", "movie": {"title": "Inception"}},
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "started"


def test_arr_cleanup_sonarr():
    with patch("src.main.cleanup.run"):
        resp = client.post(
            "/discover/arr/cleanup",
            json={"eventType": "Download", "series": {"title": "The Bear"}},
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "started"


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
