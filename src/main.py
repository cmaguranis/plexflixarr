from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.arr_controller import router as arr_router
from src.config import Settings
from src.discover.discover_controller import router as discover_router
from src.dummy import ensure_template
from src.ingestion.ingestion_controller import router as ingestion_router
from src.logging_config import setup_logging

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = Settings()
    # ensure_template(config.TEMPLATE_FILE)
    yield


app = FastAPI(title="plexflixarr", lifespan=lifespan)

app.include_router(arr_router)
app.include_router(ingestion_router)
app.include_router(discover_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/config/env")
def config_env() -> dict:
    return Settings().model_dump()
