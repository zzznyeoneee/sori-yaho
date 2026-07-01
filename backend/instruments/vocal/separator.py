"""Isolate vocal track from mixed audio using Demucs."""
import subprocess
from pathlib import Path


def separate_vocal(audio_path: str, output_dir: str) -> str:
    """
    audio_path:  입력 오디오 파일 절대 경로 (.mp3 / .wav)
    output_dir:  결과 저장 폴더
    반환값:      분리된 보컬 트랙 .wav 절대 경로
    """
    audio_path = Path(audio_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    import torch
    device = "cuda" if torch.cuda.is_available() else "cpu"

    result = subprocess.run(
        [
            "python3", "-m", "demucs",
            "--two-stems", "vocals",
            "-d", device,
            "-o", str(output_dir),
            str(audio_path),
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"Demucs 실패 (exit {result.returncode}):\n"
            f"STDOUT: {result.stdout}\n"
            f"STDERR: {result.stderr}"
        )

    matches = list(output_dir.rglob("vocals.wav"))
    if not matches:
        raise RuntimeError(
            f"vocals.wav 를 찾을 수 없습니다. output_dir: {output_dir}\n"
            f"STDOUT: {result.stdout}"
        )

    return str(matches[0])
