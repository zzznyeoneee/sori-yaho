# backend/main.py
Set-Content -Path "backend\main.py" -Encoding UTF8 -Value @'
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="Sori-Yaho API",
    description="Audio to sheet music transcription — Drums & Guitar",
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
'@

# backend/core/__init__.py
New-Item -Path "backend\core\__init__.py" -Force | Out-Null

# backend/core/config.py
Set-Content -Path "backend\core\config.py" -Encoding UTF8 -Value @'
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]
    UPLOAD_DIR: str = "/tmp/sori-yaho/uploads"
    MAX_FILE_SIZE_MB: int = 50

    class Config:
        env_file = ".env"


settings = Settings()
'@

# backend/schemas/__init__.py
New-Item -Path "backend\schemas\__init__.py" -Force | Out-Null

# backend/schemas/transcribe.py
Set-Content -Path "backend\schemas\transcribe.py" -Encoding UTF8 -Value @'
from pydantic import BaseModel
from typing import Literal


class TranscribeRequest(BaseModel):
    task_id: str
    instrument: Literal["drums", "guitar"]


class TranscribeResponse(BaseModel):
    success: bool
    error: str | None = None
    task_id: str
    status: str
    midi_url: str | None = None
    musicxml_url: str | None = None
'@

# backend/api/__init__.py
New-Item -Path "backend\api\__init__.py" -Force | Out-Null

# backend/api/routers/__init__.py
New-Item -Path "backend\api\routers\__init__.py" -Force | Out-Null

# backend/instruments/__init__.py
New-Item -Path "backend\instruments\__init__.py" -Force | Out-Null

# backend/instruments/drums/__init__.py
New-Item -Path "backend\instruments\drums\__init__.py" -Force | Out-Null

# backend/instruments/drums/separator.py
Set-Content -Path "backend\instruments\drums\separator.py" -Encoding UTF8 -Value @'
"""Isolate drum track from mixed audio using Demucs."""
import subprocess
from pathlib import Path


def separate_drums(audio_path: str, output_dir: str) -> str:
    audio_path = Path(audio_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    subprocess.run(
        [
            "python", "-m", "demucs",
            "--two-stems", "drums",
            "-o", str(output_dir),
            str(audio_path),
        ],
        check=True,
    )

    drum_wav = output_dir / "htdemucs" / audio_path.stem / "drums.wav"
    return str(drum_wav)
'@

# backend/instruments/drums/transcriber.py
Set-Content -Path "backend\instruments\drums\transcriber.py" -Encoding UTF8 -Value @'
"""Drum onset detection and MIDI generation."""
import pretty_midi
from pathlib import Path

DRUM_MAP = {
    "kick":     36,
    "snare":    38,
    "hihat_cl": 42,
    "hihat_op": 46,
    "crash":    49,
    "ride":     51,
    "tom_hi":   48,
    "tom_mid":  45,
    "tom_lo":   41,
}


def transcribe_drums(drum_wav_path: str, output_dir: str) -> str:
    import librosa

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    y, sr = librosa.load(drum_wav_path, sr=44100)
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    onset_frames = librosa.onset.onset_detect(y=y, sr=sr, units="time")

    midi = pretty_midi.PrettyMIDI(initial_tempo=float(tempo))
    drum_inst = pretty_midi.Instrument(program=0, is_drum=True, name="Drums")

    for onset in onset_frames:
        note = pretty_midi.Note(
            velocity=100,
            pitch=DRUM_MAP["snare"],
            start=float(onset),
            end=float(onset) + 0.1,
        )
        drum_inst.notes.append(note)

    midi.instruments.append(drum_inst)

    out_path = output_dir / f"{Path(drum_wav_path).stem}_drums.mid"
    midi.write(str(out_path))
    return str(out_path)
'@

# backend/instruments/drums/notator.py
Set-Content -Path "backend\instruments\drums\notator.py" -Encoding UTF8 -Value @'
"""Convert drum MIDI to MusicXML notation."""
from music21 import converter
from pathlib import Path


def midi_to_drum_score(midi_path: str, output_dir: str) -> str:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    score = converter.parse(midi_path)
    out_path = output_dir / f"{Path(midi_path).stem}.xml"
    score.write("musicxml", fp=str(out_path))
    return str(out_path)
'@

# backend/instruments/guitar/__init__.py
Set-Content -Path "backend\instruments\guitar\__init__.py" -Encoding UTF8 -Value "# Phase 2 - Guitar chord detection & TAB generation"

# backend/pyproject.toml
Set-Content -Path "backend\pyproject.toml" -Encoding UTF8 -Value @'
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "sori-yaho-backend"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "fastapi>=0.111",
    "uvicorn[standard]>=0.29",
    "pydantic>=2.7",
    "pydantic-settings>=2.3",
    "python-multipart>=0.0.9",
    "demucs>=4.0",
    "madmom>=0.16",
    "librosa>=0.10",
    "soundfile>=0.12",
    "pretty_midi>=0.2.10",
    "music21>=9.1",
    "mido>=1.3",
    "basic-pitch>=0.3",
]

[project.optional-dependencies]
dev = [
    "pytest>=8",
    "httpx>=0.27",
]
'@

# backend/.env.example
Set-Content -Path "backend\.env.example" -Encoding UTF8 -Value @'
CORS_ORIGINS=["http://localhost:3000"]
UPLOAD_DIR=/tmp/sori-yaho/uploads
MAX_FILE_SIZE_MB=50
'@

# document/01_overview.md
Set-Content -Path "document\01_overview.md" -Encoding UTF8 -Value @'
# 01. 프로젝트 개요 및 아키텍처

## 서비스 소개

**서비스명:** Sori-Yaho

**목적:**
음원(MP3/WAV)을 업로드하면 악기별로 자동 채보하여 MIDI + 악보(MusicXML) 파일을 생성한다.

## 개발 단계

| Phase | 악기 | 핵심 기능 |
|---|---|---|
| 1 | 드럼 | 오디오 → 드럼 트랙 분리 → MIDI + 악보 생성 |
| 2 | 기타 | 오디오 → 코드 진행 채보 → 코드 차트 생성 |
| 3 | 기타 확장 | 멜로디 TAB 생성 |

## 데이터 흐름
