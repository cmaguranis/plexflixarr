import threading
from collections.abc import Callable

from fastapi import APIRouter, BackgroundTasks

from src.ingestion import simkl_lists_sync

router = APIRouter(prefix="/ingestion")

_ingest_lock = threading.Lock()


def _with_lock(fn: Callable, lock: threading.Lock) -> Callable:
    def task() -> None:
        try:
            fn()
        finally:
            lock.release()

    return task


@router.post("/simkl_lists")
def simkl_lists_endpoint(background_tasks: BackgroundTasks) -> dict:
    if not _ingest_lock.acquire(blocking=False):
        return {"status": "already_running"}
    background_tasks.add_task(_with_lock(simkl_lists_sync.run, _ingest_lock))
    return {"status": "started"}
