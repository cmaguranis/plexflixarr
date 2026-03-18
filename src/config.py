from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
    )

    # Plex
    PLEX_URL: str = "http://localhost:32400"
    PLEX_TOKEN: str = ""

    # TMDB
    TMDB_API_KEY: str = ""
    TMDB_REQUEST_DELAY: float = 0.3  # seconds between TMDB API requests

    # TVDB
    TVDB_API_KEY: str = ""

    # Simkl curated list names (used as DB keys)
    SIMKL_LIST_NAME_KDRAMAS: str = "K-Dramas"
    SIMKL_LIST_NAME_KREALITY: str = "Korean Reality"
    SIMKL_LIST_NAME_REALITY: str = "Reality TV"
    SIMKL_LIST_NAME_KMOVIES: str = "Korean Movies"

    # Simkl trending list names
    SIMKL_LIST_NAME_TRENDING_TV: str = "Trending TV"
    SIMKL_LIST_NAME_TRENDING_MOVIES: str = "Trending Movies"
    SIMKL_LIST_NAME_TRENDING_ANIME: str = "Trending Anime"

    # Simkl
    SIMKL_CLIENT_ID: str = ""
    SIMKL_FALLBACK_CLIENT_ID: str = ""  # fallback client ID in case the first gets rate limited
    SIMKL_REQUEST_DELAY: float = 0.3  # seconds between API requests

    # Timezone (IANA, e.g. "America/New_York") used for timestamps
    TIMEZONE: str = "America/New_York"

    # Plex library sections
    DISCOVER_MOVIES_LIB: str = "Movies"
    DISCOVER_SHOWS_LIB: str = "TV Shows"
    REAL_LIBS: list[str] = []

    # Filesystem paths
    SIMKL_LISTS_DB_FILE: Path = Path("data/simkl_lists.db")


settings = Settings()
