import threading
from contextlib import asynccontextmanager
from typing import Any

from fastapi import APIRouter, BackgroundTasks, FastAPI

from src.config import Settings
from src.dummy import ensure_template
from src.jobs import cleanup, dedupe, ingestion, label
from src.jobs.ingestion import MediaItem, fetch_media
from src.logging_config import setup_logging

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = Settings()
    ensure_template(config.TEMPLATE_FILE)
    yield


app = FastAPI(title="plexflixarr", lifespan=lifespan)

# Prevent overlapping ingest runs
_ingest_lock = threading.Lock()

ingestion_router = APIRouter(prefix="/ingestion")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/config/env")
def config_env() -> dict:
    return Settings().model_dump()


@ingestion_router.post("/fetch")
def fetch_candidates() -> list[MediaItem]:
    """Fetch raw candidates from TMDB and Trakt without filtering or writing files."""
    items = fetch_media(Settings())
    return items


@ingestion_router.post("/run")
def trigger_ingest(background_tasks: BackgroundTasks) -> dict:
    if not _ingest_lock.acquire(blocking=False):
        return {"status": "already_running"}

    def _run() -> None:
        try:
            ingestion.run()
            dedupe.run()
        finally:
            _ingest_lock.release()

    background_tasks.add_task(_run)
    return {"status": "started"}


app.include_router(ingestion_router)


@app.post("/discover/arr/cleanup")
async def arr_cleanup(payload: dict[str, Any], background_tasks: BackgroundTasks) -> dict:
    """Receives webhooks from Radarr/Sonarr.

    Handles eventType=Download for both imports and upgrades (isUpgrade true/false).
    """
    if payload.get("eventType") == "Test":
        return {"status": "ok", "reason": "test event"}
    if payload.get("eventType") != "Download":
        return {"status": "ignored", "reason": f"Unhandled eventType: {payload.get('eventType')}"}
    background_tasks.add_task(cleanup.run, payload)
    return {"status": "started", "source": "arr"}


@app.post("/dummy/dedupe")
def trigger_dedupe(background_tasks: BackgroundTasks) -> dict:
    """Remove all discover-library dummies that already exist in real Plex libraries."""
    background_tasks.add_task(dedupe.run)
    return {"status": "started"}


@app.post("/discover/label")
def trigger_label(background_tasks: BackgroundTasks) -> dict:
    """Apply missing Discover_* labels to unlabelled items in the Discover libraries."""
    background_tasks.add_task(label.run)
    return {"status": "started"}
