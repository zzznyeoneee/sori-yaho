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

# 주파수 대역 (Hz)
_KICK_MAX_HZ  = 250
_SNARE_MAX_HZ = 8000


def _classify_onset(y: np.ndarray, sr: int, onset_sample: int, frame_len: int = 1024) -> str:
    """
    onset 직후 짧은 구간의 주파수 에너지 분포로 kick/snare/hihat 구분.
    - kick:  저역(< 250 Hz) 에너지 비율이 높음
    - hihat: 고역(> 8 kHz) 에너지 비율이 높음
    - snare: 그 외 (중역 + 노이즈)
    """
    frame = y[onset_sample: onset_sample + frame_len]
    if len(frame) < frame_len:
        frame = np.pad(frame, (0, frame_len - len(frame)))

    magnitude = np.abs(np.fft.rfft(frame))
    freqs = np.fft.rfftfreq(frame_len, d=1.0 / sr)

    total = magnitude.sum() + 1e-9
    kick_ratio  = magnitude[freqs <  _KICK_MAX_HZ].sum()  / total
    hihat_ratio = magnitude[freqs > _SNARE_MAX_HZ].sum() / total

    if kick_ratio > 0.55:
        return "kick"
    if hihat_ratio > 0.40:
        return "hihat_cl"
    return "snare"


def transcribe_drums(drum_wav_path: str, output_dir: str) -> str:
    """
    drum_wav_path:  분리된 드럼 트랙 .wav 경로
    output_dir:     결과 저장 폴더
    반환값:         생성된 .mid 파일 절대 경로
    """
    import librosa

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    y, sr = librosa.load(drum_wav_path, sr=44100, mono=True)
    tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
    onset_times = librosa.onset.onset_detect(y=y, sr=sr, units="time")
    onset_samples = librosa.onset.onset_detect(y=y, sr=sr, units="samples")

    bpm = float(np.atleast_1d(tempo)[0])
    midi = pretty_midi.PrettyMIDI(initial_tempo=bpm)
    drum_inst = pretty_midi.Instrument(program=0, is_drum=True, name="Drums")

    for onset_time, onset_sample in zip(onset_times, onset_samples):
        drum_type = _classify_onset(y, sr, int(onset_sample))
        note = pretty_midi.Note(
            velocity=100,
            pitch=DRUM_MAP[drum_type],
            start=float(onset_time),
            end=float(onset_time) + 0.05,
        )
        drum_inst.notes.append(note)

    midi.instruments.append(drum_inst)

    stem = Path(drum_wav_path).stem
    out_path = output_dir / f"{stem}_drums.mid"
    midi.write(str(out_path))
    return str(out_path)
