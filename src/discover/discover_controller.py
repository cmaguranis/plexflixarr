from typing import Any

from fastapi import APIRouter, BackgroundTasks

from src.discover import cleanup, dedupe, label

router = APIRouter(prefix="/discover")


@router.post("/arr/cleanup")
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


@router.post("/dedupe")
def trigger_dedupe(background_tasks: BackgroundTasks) -> dict:
    """Remove all discover-library dummies that already exist in real Plex libraries."""
    background_tasks.add_task(dedupe.run)
    return {"status": "started"}


@router.post("/label")
def trigger_label(background_tasks: BackgroundTasks) -> dict:
    """Apply missing Discover_* labels to unlabelled items in the Discover libraries."""
    background_tasks.add_task(label.run)
    return {"status": "started"}
