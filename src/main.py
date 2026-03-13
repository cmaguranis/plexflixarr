import threading
from contextlib import asynccontextmanager

from fastapi import APIRouter, BackgroundTasks, FastAPI
from pydantic import BaseModel

from src.config import Settings
from src.dummy import ensure_template
from src.jobs import cleanup, dedupe, ingestion, label
from src.jobs.ingestion import MediaItem, fetch_media
from src.logging_config import setup_logging

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_template(Settings().TEMPLATE_FILE)
    yield


app = FastAPI(title="plexflixarr", lifespan=lifespan)

# Prevent overlapping ingest runs
_ingest_lock = threading.Lock()

ingestion_router = APIRouter(prefix="/ingestion")


class CleanupRequest(BaseModel):
    media_type: str  # "episode" or "movie"
    title: str
    show_name: str | None = None


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/config/env")
def config_env() -> dict:
    return Settings().model_dump()


@ingestion_router.post("/fetch")
def fetch_candidates() -> list[MediaItem]:
    """Fetch raw candidates from TMDB and Trakt without filtering or writing files."""
    items, _ = fetch_media(Settings())
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


@app.post("/dummy_cleanup")
def trigger_cleanup(body: CleanupRequest, background_tasks: BackgroundTasks) -> dict:
    background_tasks.add_task(cleanup.run, body.media_type, body.title, body.show_name)
    return {"status": "started", "media_type": body.media_type, "title": body.title}


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
