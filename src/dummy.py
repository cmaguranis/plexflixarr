import logging
import re
import shutil
import subprocess
from pathlib import Path

from src.config import Settings

logger = logging.getLogger(__name__)

_SANITIZE_RE = re.compile(r'[\\/*?:"<>|]')


def sanitize_filename(title: str) -> str:
    return _SANITIZE_RE.sub("", str(title)).strip()


def ensure_template(path: Path) -> None:
    """Generate a 1-second black-screen silent .mkv if the template does not exist."""
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Generating dummy template at %s", path)
    result = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=size=1920x1080:rate=24:color=black",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-t",
            "1",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr}")
    logger.info("Template created at %s", path)


def create_dummy(title: str, year: str | None, media_type: str, config: Settings) -> Path | None:
    """
    Create a dummy media folder + file for the given title.

    Returns the created folder Path, or None if skipped (already exists or no year).
    """
    if not year or str(year) == "Unknown":
        return None

    folder_name = f"{sanitize_filename(title)} ({year})"

    if media_type in ("movie", "movies"):
        discover_path = config.DISCOVER_MOVIES_PATH / folder_name
        if discover_path.exists():
            return None
        discover_path.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(config.TEMPLATE_FILE, discover_path / f"{folder_name}.mkv")
        logger.info("Created movie dummy: %s", folder_name)
        return discover_path

    if media_type in ("show", "shows", "tv"):
        discover_path = config.DISCOVER_SHOWS_PATH / folder_name
        if discover_path.exists():
            return None
        season_dir = discover_path / "Season 01"
        season_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(config.TEMPLATE_FILE, season_dir / f"{folder_name} - S01E01.mkv")
        logger.info("Created show dummy: %s", folder_name)
        return discover_path

    return None


def item_folder(item, libtype: str, config: Settings) -> Path:
    """Resolve the OS folder path for a Plex dummy item."""
    base = config.DISCOVER_MOVIES_PATH if libtype == "movie" else config.DISCOVER_SHOWS_PATH
    loc = Path(item.locations[0])
    folder_name = loc.parent.name if libtype == "movie" else loc.name
    return base / folder_name


def delete_dummy(folder: Path) -> None:
    """Permanently remove a dummy media folder from the filesystem."""
    if folder.exists():
        shutil.rmtree(folder)
        logger.info("Deleted dummy folder: %s", folder)
    else:
        logger.warning("Dummy folder not found, skipping delete: %s", folder)
