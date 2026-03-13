from unittest.mock import MagicMock, patch

from src.clients.anilist_client import AniListClient


def _mock_response(payload: dict) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = payload
    return resp


def _rec_node(title_en=None, title_ro="Naruto", year=2002, fmt="TV") -> dict:
    return {
        "mediaRecommendation": {
            "title": {"english": title_en, "romaji": title_ro},
            "seasonYear": year,
            "format": fmt,
        }
    }


def _payload(nodes: list[dict]) -> dict:
    return {
        "data": {
            "MediaListCollection": {
                "lists": [
                    {
                        "entries": [
                            {
                                "media": {
                                    "title": {"english": "Source Anime", "romaji": "Source Anime"},
                                    "recommendations": {"nodes": nodes},
                                }
                            }
                        ]
                    }
                ]
            }
        }
    }


def test_fetch_recommendations_returns_show(config):
    with (
        patch("src.clients.anilist_client.requests.post", return_value=_mock_response(_payload([_rec_node(title_en="Naruto", fmt="TV")]))),
        patch("src.clients.anilist_client.time.sleep"),
    ):
        results = AniListClient(config).fetch_recommendations("testuser")

    assert len(results) == 1
    assert results[0].title == "Naruto"
    assert results[0].media_type == "show"
    assert results[0].year == "2002"


def test_fetch_recommendations_returns_movie(config):
    with (
        patch("src.clients.anilist_client.requests.post", return_value=_mock_response(_payload([_rec_node(title_en="Spirited Away", year=2001, fmt="MOVIE")]))),
        patch("src.clients.anilist_client.time.sleep"),
    ):
        results = AniListClient(config).fetch_recommendations("testuser")

    assert results[0].media_type == "movie"


def test_fetch_recommendations_uses_romaji_fallback(config):
    with (
        patch("src.clients.anilist_client.requests.post", return_value=_mock_response(_payload([_rec_node(title_en=None, title_ro="Kimetsu no Yaiba")]))),
        patch("src.clients.anilist_client.time.sleep"),
    ):
        results = AniListClient(config).fetch_recommendations("testuser")

    assert results[0].title == "Kimetsu no Yaiba"


def test_fetch_recommendations_skips_unknown_formats(config):
    nodes = [
        _rec_node(title_en="Music Video", fmt="MUSIC"),
        _rec_node(title_en="Attack on Titan", fmt="TV"),
    ]
    with (
        patch("src.clients.anilist_client.requests.post", return_value=_mock_response(_payload(nodes))),
        patch("src.clients.anilist_client.time.sleep"),
    ):
        results = AniListClient(config).fetch_recommendations("testuser")

    assert len(results) == 1
    assert results[0].title == "Attack on Titan"


def test_fetch_recommendations_deduplicates(config):
    # Same anime recommended from two different source entries
    nodes = [
        _rec_node(title_en="My Hero Academia", year=2016, fmt="TV"),
        _rec_node(title_en="My Hero Academia", year=2016, fmt="TV"),
    ]
    with (
        patch("src.clients.anilist_client.requests.post", return_value=_mock_response(_payload(nodes))),
        patch("src.clients.anilist_client.time.sleep"),
    ):
        results = AniListClient(config).fetch_recommendations("testuser")

    assert len(results) == 1


def test_fetch_recommendations_handles_missing_year(config):
    with (
        patch("src.clients.anilist_client.requests.post", return_value=_mock_response(_payload([_rec_node(year=None)]))),
        patch("src.clients.anilist_client.time.sleep"),
    ):
        results = AniListClient(config).fetch_recommendations("testuser")

    assert results[0].year is None


def test_fetch_recommendations_handles_api_error(config):
    with (
        patch("src.clients.anilist_client.requests.post", side_effect=Exception("network error")),
        patch("src.clients.anilist_client.time.sleep"),
    ):
        results = AniListClient(config).fetch_recommendations("testuser")

    assert results == []


def test_fetch_recommendations_skips_null_recs(config):
    nodes = [
        {"mediaRecommendation": None},
        _rec_node(title_en="Fullmetal Alchemist", fmt="TV"),
    ]
    with (
        patch("src.clients.anilist_client.requests.post", return_value=_mock_response(_payload(nodes))),
        patch("src.clients.anilist_client.time.sleep"),
    ):
        results = AniListClient(config).fetch_recommendations("testuser")

    assert len(results) == 1
    assert results[0].title == "Fullmetal Alchemist"
