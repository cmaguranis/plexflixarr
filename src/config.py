from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Plex
    PLEX_URL: str = "http://localhost:32400"
    PLEX_TOKEN: str = ""

    # TMDB
    TMDB_API_KEY: str = ""

    # Trakt
    TRAKT_CLIENT_ID: str = ""
    TRAKT_USERNAME: str = ""  # Required for Couchmoney themed list discovery

    # AniList
    ANILIST_USERNAME: str = ""        # Required for personalised anime recommendations
    ANILIST_RECS_PER_ENTRY: int = 3   # Recommendations fetched per completed anime title

    # TMDB quality gate
    TMDB_MIN_VOTE_AVERAGE: float = 6.0
    TMDB_MIN_VOTE_COUNT: int = 100
    # ISO 639-1 language codes to exclude from TMDB results (Trakt/AniList items are unaffected)
    EXCLUDED_LANGUAGES: list[str] = ["hi", "ta", "te", "ml", "kn", "bn", "mr"]

    # Filesystem paths
    TEMPLATE_FILE: Path = Path("assets/dummy.mkv")
    DISCOVER_MOVIES_PATH: Path = Path("/media/discover_movies")
    DISCOVER_SHOWS_PATH: Path = Path("/media/discover_shows")
    KOMETA_CONFIG_PATH: Path = Path("kometa-config")  # Directory where discovery_ui.yml is written

    # Real Plex library names used to skip duplicates during ingestion
    REAL_MOVIES_LIBS: list[str] = ["Movies", "Anime Movies"]
    REAL_SHOWS_LIBS: list[str] = ["TV Shows", "Anime TV"]

    # Ingestion tuning
    PAGES_PER_PROVIDER: int = 5
    STREAMING_PROVIDERS: dict[str, str] = {
        "8": "Discover_Netflix",
        "15": "Discover_Hulu",
        "350": "Discover_AppleTV",
        "384": "Discover_Max",
        "526": "Discover_AMC",
        "283": "Discover_Crunchyroll",
        "337": "Discover_Disney",
        "80": "Discover_AdultSwim",
    }
    # TMDB genre IDs → Plex label  (https://www.themoviedb.org/talk/5daf6eb0ae36680011d7e6ee)
    DISCOVER_GENRES: dict[str, str] = {
        "28": "Discover_Action",
        "35": "Discover_Comedy",
        "18": "Discover_Drama",
        "27": "Discover_Horror",
        "878": "Discover_SciFi",
        "10749": "Discover_Romance",
        "16": "Discover_Animation",
        "99": "Discover_Documentary",
    }


settings = Settings()
