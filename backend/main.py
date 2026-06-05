from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from pathlib import Path

from core.config import settings
from api.routers import transcribe


@asynccontextmanager
async def lifespan(app: FastAPI):
    Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    Path(settings.OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title="Sori-Yaho API",
    description="Audio to sheet music transcription — Drums, Piano & Guitar",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(transcribe.router, prefix="/api")

app.mount("/files", StaticFiles(directory=settings.OUTPUT_DIR), name="files")


@app.get("/health")
async def health():
    return {"status": "ok"}
