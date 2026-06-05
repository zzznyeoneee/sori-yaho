"""POST /api/transcribe — 음원 파일을 받아 악기별 파이프라인 실행"""
import uuid
import shutil
from pathlib import Path

from fastapi import APIRouter, File, Form, UploadFile, HTTPException
from typing import Literal

from core.config import settings
from schemas.transcribe import TranscribeResponse

router = APIRouter()

ALLOWED_EXTENSIONS = {".mp3", ".wav", ".flac", ".m4a"}
MAX_BYTES = settings.MAX_FILE_SIZE_MB * 1024 * 1024


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe(
    file: UploadFile = File(...),
    instrument: Literal["drums", "piano"] = Form("drums"),
):
    # 파일 확장자 검사
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"지원하지 않는 파일 형식입니다: {suffix}")

    # 파일 크기 검사
    content = await file.read()
    if len(content) > MAX_BYTES:
        raise HTTPException(status_code=413, detail=f"파일 크기가 {settings.MAX_FILE_SIZE_MB}MB를 초과합니다.")

    task_id = uuid.uuid4().hex
    upload_dir = Path(settings.UPLOAD_DIR) / task_id
    output_dir = Path(settings.OUTPUT_DIR) / task_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    audio_path = upload_dir / f"input{suffix}"
    audio_path.write_bytes(content)

    try:
        if instrument == "drums":
            midi_path, xml_path = _run_drums(str(audio_path), str(output_dir))
        elif instrument == "piano":
            midi_path, xml_path = _run_piano(str(audio_path), str(output_dir))
        else:
            raise HTTPException(status_code=400, detail=f"지원하지 않는 악기입니다: {instrument}")
    except Exception as e:
        shutil.rmtree(upload_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=str(e))

    midi_rel = Path(midi_path).relative_to(settings.OUTPUT_DIR)
    xml_rel = Path(xml_path).relative_to(settings.OUTPUT_DIR)

    return TranscribeResponse(
        success=True,
        task_id=task_id,
        instrument=instrument,
        midi_url=f"/files/{midi_rel}",
        musicxml_url=f"/files/{xml_rel}",
    )


def _run_drums(audio_path: str, output_dir: str):
    from instruments.drums.separator import separate_drums
    from instruments.drums.transcriber import transcribe_drums
    from instruments.drums.notator import midi_to_drum_score

    drum_wav = separate_drums(audio_path, output_dir)
    midi_path = transcribe_drums(drum_wav, output_dir)
    xml_path = midi_to_drum_score(midi_path, output_dir)
    return midi_path, xml_path


def _run_piano(audio_path: str, output_dir: str):
    from instruments.piano.converter import audio_to_midi, midi_to_musicxml

    midi_path = audio_to_midi(audio_path, output_dir)
    xml_path = midi_to_musicxml(midi_path, output_dir)
    return midi_path, xml_path
