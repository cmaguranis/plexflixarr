from fastapi import APIRouter

from src.arr import arr_service
from src.config import Settings

router = APIRouter(prefix="/arr")


@router.get("/lists")
def get_lists() -> list[dict]:
    return arr_service.get_list_names_with_counts(Settings())


@router.get("/lists/{name}")
def get_list(name: str, limit: int | None = None) -> list[dict]:
    items = arr_service.get_list_items(name, Settings())
    return items[:limit] if limit else items


@router.post("/kometa_complete")
def kometa_complete() -> dict:
    return arr_service.build_curated_collections(Settings())
