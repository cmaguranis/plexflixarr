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
    ANILIST_USERNAME: str = ""  # Required for personalised anime recommendations
    ANILIST_RECS_PER_ENTRY: int = 3  # Recommendations fetched per completed anime title

    # TMDB quality gate
    TMDB_QUALITY_GATE: bool = True
    TMDB_MIN_VOTE_AVERAGE: float = 6.2
    TMDB_MIN_VOTE_COUNT: int = 100
    TMDB_REQUEST_DELAY: float = 0.3  # seconds between TMDB API requests
    # ISO 639-1 language codes whose items skip the quality gate entirely
    QUALITY_GATE_BYPASS_LANGUAGES: list[str] = ["ko"]

    # MDBList list management
    MDBLIST_USERNAME: str = ""

    # Simkl curated list names (used as DB keys and MDBList list names)
    SIMKL_LIST_NAME_KDRAMAS: str = "K-Dramas"
    SIMKL_LIST_NAME_KREALITY: str = "Korean Reality"
    SIMKL_LIST_NAME_REALITY: str = "Reality TV"

    # Simkl
    SIMKL_CLIENT_ID: str = ""
    SIMKL_FALLBACK_CLIENT_ID: str = ""  # fallback client ID in case the first gets rate limited
    SIMKL_REQUEST_DELAY: float = 0.3  # seconds between API requests

    # MDBList quality gate (used by MdblistClient standalone — not ingestion)
    MDBLIST_API_KEY: str = ""
    MDBLIST_MIN_TRAKT: int = 60  # Trakt popularity score threshold (0–100)
    MDBLIST_MIN_RATING: int = 60  # Rotten Tomatoes score threshold (0–100)

    # ISO 639-1 language codes to exclude from TMDB results (Trakt/AniList items are unaffected)
    EXCLUDED_LANGUAGES: list[str] = ["hi", "ta", "te", "ml", "kn", "bn", "mr"]

    # Timezone (IANA, e.g. "America/New_York") used for timestamps
    TIMEZONE: str = "America/New_York"

    # Filesystem paths
    STATE_FILE: Path = Path("data/state.json")
    SIMKL_LISTS_DB_FILE: Path = Path("data/simkl_lists.db")
    SEED_CACHE_FILE: Path = Path("data/seed_cache.json")
    SEED_CACHE_TTL_HOURS: int = 23  # reuse cached seed data within this window
    SIMKL_ID_CACHE_FILE: Path = Path("data/simkl_id_cache.json")
    TEMPLATE_FILE: Path = Path("assets/dummy.mkv")
    DISCOVER_MOVIES_PATH: Path = Path("/media/discover_movies")
    DISCOVER_SHOWS_PATH: Path = Path("/media/discover_shows")
    KOMETA_CONFIG_PATH: Path = Path("kometa-config")  # Directory where discovery_ui.yml is written

    # Discover Plex library names
    DISCOVER_MOVIES_LIB: str = "Movies"
    DISCOVER_SHOWS_LIB: str = "TV Shows"

    # Real Plex library names used to skip duplicates during ingestion
    REAL_LIBS: list[str] = ["Movies", "Anime Movies", "TV Shows", "Anime TV"]

    # Ingestion tuning
    PAGES_PER_PROVIDER: int = 5
    STREAMING_PROVIDERS: dict[str, str] = {
        "8": "Provider_Netflix",
        "15": "Provider_Hulu",
        "350": "Provider_AppleTV",
        "384": "Provider_Max",
        "526": "Provider_AMC",
        "283": "Provider_Crunchyroll",
        "337": "Provider_Disney",
        "80": "Provider_AdultSwim",
    }


settings = Settings()
