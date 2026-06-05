"""Isolate drum track from mixed audio using Demucs."""
import subprocess
from pathlib import Path


def separate_drums(audio_path: str, output_dir: str) -> str:
    """
    audio_path:  입력 오디오 파일 절대 경로 (.mp3 / .wav)
    output_dir:  결과 저장 폴더
    반환값:      분리된 드럼 트랙 .wav 절대 경로
    """
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

    # Demucs outputs to output_dir/htdemucs/<stem>/<filename>.wav
    drum_wav = output_dir / "htdemucs" / audio_path.stem / "drums.wav"
    return str(drum_wav)
