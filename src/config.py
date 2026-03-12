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

    # MDBList quality gate
    MDBLIST_API_KEY: str = ""
    MDBLIST_MIN_TRAKT: int = 70
    MDBLIST_MIN_RT: int = 60

    # Sonarr / Radarr
    SONARR_BASEURL: str = "http://localhost:8989"
    SONARR_API_KEY: str = ""
    RADARR_BASEURL: str = "http://localhost:7878"
    RADARR_API_KEY: str = ""

    # Filesystem paths
    TEMPLATE_FILE: Path = Path("assets/dummy.mkv")
    DISCOVER_MOVIES_PATH: Path = Path("/media/discover_movies")
    DISCOVER_SHOWS_PATH: Path = Path("/media/discover_shows")
    REAL_MOVIES_PATH: Path = Path("/media/real_movies")
    REAL_SHOWS_PATH: Path = Path("/media/real_shows")

    # Ingestion tuning
    PAGES_PER_PROVIDER: int = 5
    STREAMING_PROVIDERS: dict[str, str] = {
        "8": "Discover_Netflix",
        "15": "Discover_Hulu",
        "350": "Discover_AppleTV",
        "384": "Discover_Max",
    }


# Module-level singleton — used directly by new code via `from src.config import settings`
settings = Settings()

# Callable wrappers for compatibility with existing sonarr_client / radarr_client
# which call e.g. config.SONARR_BASEURL()
SONARR_BASEURL = lambda: settings.SONARR_BASEURL  # noqa: E731
SONARR_API_KEY = lambda: settings.SONARR_API_KEY  # noqa: E731
RADARR_BASEURL = lambda: settings.RADARR_BASEURL  # noqa: E731
RADARR_API_KEY = lambda: settings.RADARR_API_KEY  # noqa: E731
