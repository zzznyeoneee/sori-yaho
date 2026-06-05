<<<<<<< HEAD
﻿from fastapi import FastAPI
=======
from fastapi import FastAPI
>>>>>>> 7c418751c71fd61627f81bd3fe4fb9a2a46d8869
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
<<<<<<< HEAD
    yield
=======
    # startup
    yield
    # shutdown
>>>>>>> 7c418751c71fd61627f81bd3fe4fb9a2a46d8869


app = FastAPI(
    title="Sori-Yaho API",
<<<<<<< HEAD
    description="Audio to sheet music transcription ??Drums & Guitar",
=======
    description="Audio to sheet music transcription — Drums & Guitar",
>>>>>>> 7c418751c71fd61627f81bd3fe4fb9a2a46d8869
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


@app.get("/health")
async def health():
    return {"status": "ok"}
