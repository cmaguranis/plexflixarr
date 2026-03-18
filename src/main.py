from fastapi import FastAPI

from src.arr.arr_controller import router as arr_router
from src.ingestion.ingestion_controller import router as ingestion_router
from src.logging_config import setup_logging

setup_logging()

app = FastAPI(title="plexflixarr")

app.include_router(arr_router)
app.include_router(ingestion_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/config/env")
def config_env() -> dict:
    from src.config import Settings

    return Settings().model_dump()
