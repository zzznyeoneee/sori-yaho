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
