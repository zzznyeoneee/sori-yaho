"""Drum transcription using Omnizart for multi-instrument classification."""
from pathlib import Path


def transcribe_drums(drum_wav_path: str, output_dir: str) -> str:
    """
    drum_wav_path:  분리된 드럼 트랙 .wav 경로
    output_dir:     결과 저장 폴더
    반환값:         생성된 .mid 파일 절대 경로
    """
    from omnizart.drum import app as drum_app

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Omnizart가 같은 폴더에 <stem>.mid 생성
    midi_path = drum_app.transcribe(drum_wav_path, output=str(output_dir))

    # 반환값이 없는 경우 직접 경로 추정
    if midi_path is None:
        stem = Path(drum_wav_path).stem
        midi_path = str(output_dir / f"{stem}.mid")

    return str(midi_path)
