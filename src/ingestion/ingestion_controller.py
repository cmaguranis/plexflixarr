import threading
from collections.abc import Callable

from fastapi import APIRouter, BackgroundTasks

from src.config import Settings
from src.ingestion import ingestion, seed, simkl_lists_sync

router = APIRouter(prefix="/ingestion")

_ingest_lock = threading.Lock()


def _with_lock(fn: Callable, lock: threading.Lock) -> Callable:
    def task() -> None:
        try:
            fn()
        finally:
            lock.release()

    return task


@router.post("/seed")
def seed_endpoint(background_tasks: BackgroundTasks, test_run: bool = False, cache: bool = False) -> dict:
    if not _ingest_lock.acquire(blocking=False):
        return {"status": "already_running"}

    background_tasks.add_task(_with_lock(lambda: seed.run(test_run=test_run, use_cache=cache), _ingest_lock))
    return {"status": "started"}


@router.post("/run")
def trigger_ingest(background_tasks: BackgroundTasks) -> dict:
    if not _ingest_lock.acquire(blocking=False):
        return {"status": "already_running"}

    background_tasks.add_task(_with_lock(ingestion.run_with_dedupe, _ingest_lock))
    return {"status": "started"}


@router.post("/simkl_lists")
def simkl_lists_endpoint(background_tasks: BackgroundTasks) -> dict:
    if not _ingest_lock.acquire(blocking=False):
        return {"status": "already_running"}
    background_tasks.add_task(_with_lock(simkl_lists_sync.run, _ingest_lock))
    return {"status": "started"}


@router.get("/simkl-id-cache")
def get_simkl_id_cache() -> dict:
    return seed._load_id_cache(Settings().SIMKL_ID_CACHE_FILE)
