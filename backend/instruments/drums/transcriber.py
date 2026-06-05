"""Drum onset detection and MIDI generation."""
import pretty_midi
import numpy as np
from pathlib import Path

# General MIDI drum map (channel 10)
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
    """
    drum_wav_path:  분리된 드럼 트랙 .wav 경로
    output_dir:     결과 저장 폴더
    반환값:         생성된 .mid 파일 절대 경로
    """
    import librosa

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    y, sr = librosa.load(drum_wav_path, sr=44100)
    tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
    onset_frames = librosa.onset.onset_detect(y=y, sr=sr, units="time")

    midi = pretty_midi.PrettyMIDI(initial_tempo=float(tempo))
    drum_inst = pretty_midi.Instrument(program=0, is_drum=True, name="Drums")

    for onset in onset_frames:
        note = pretty_midi.Note(
            velocity=100,
            pitch=DRUM_MAP["snare"],  # placeholder — classifier will refine
            start=float(onset),
            end=float(onset) + 0.1,
        )
        drum_inst.notes.append(note)

    midi.instruments.append(drum_inst)

    stem = Path(drum_wav_path).stem
    out_path = output_dir / f"{stem}_drums.mid"
    midi.write(str(out_path))
    return str(out_path)
