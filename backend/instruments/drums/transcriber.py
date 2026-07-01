"""Drum transcription — Omnizart on Linux/WSL, spectral fallback on Windows."""
from pathlib import Path


def transcribe_drums(drum_wav_path: str, output_dir: str) -> str:
    """
    drum_wav_path:  분리된 드럼 트랙 .wav 경로
    output_dir:     결과 저장 폴더
    반환값:         생성된 .mid 파일 절대 경로
    """
    try:
        from omnizart.drum import app as drum_app
        midi_path = drum_app.transcribe(drum_wav_path, output=str(output_dir))
        if midi_path is None:
            stem = Path(drum_wav_path).stem
            midi_path = str(Path(output_dir) / f"{stem}.mid")
        return str(midi_path)
    except Exception:
        return _spectral_transcribe(drum_wav_path, output_dir)


def _spectral_transcribe(drum_wav_path: str, output_dir: str) -> str:
    """Omnizart 없을 때 spectral 분류기로 fallback."""
    import numpy as np
    import pretty_midi
    import librosa

    DRUM_MAP = {
        "kick":     36,
        "snare":    38,
        "hihat_cl": 42,
        "hihat_op": 46,
        "crash":    49,
        "tom_hi":   48,
        "tom_mid":  45,
        "tom_lo":   41,
    }

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    y, sr = librosa.load(drum_wav_path, sr=44100, mono=True)
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    bpm = float(round(np.atleast_1d(tempo)[0]))

    onset_times   = librosa.onset.onset_detect(y=y, sr=sr, units="time", delta=0.07, wait=4)
    onset_samples = librosa.onset.onset_detect(y=y, sr=sr, units="samples", delta=0.07, wait=4)

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

    bpm = float(np.atleast_1d(tempo)[0])
    midi = pretty_midi.PrettyMIDI(initial_tempo=bpm)
    
    stem = Path(drum_wav_path).stem
    out_path = output_dir / f"{stem}_drums.mid"
    midi.write(str(out_path))
    return str(out_path)


def _classify_onset(y, sr: int, onset_sample: int, frame_len: int = 2048) -> str:
    import numpy as np

    frame = y[onset_sample: onset_sample + frame_len]
    if len(frame) < frame_len:
        frame = __import__('numpy').pad(frame, (0, frame_len - len(frame)))

    magnitude = __import__('numpy').abs(__import__('numpy').fft.rfft(frame))
    freqs = __import__('numpy').fft.rfftfreq(frame_len, d=1.0 / sr)
    total = magnitude.sum() + 1e-9

    sub   = magnitude[freqs <   80].sum() / total
    low   = magnitude[(freqs >= 80)   & (freqs < 300)].sum() / total
    mid   = magnitude[(freqs >= 300)  & (freqs < 3000)].sum() / total
    vhigh = magnitude[freqs >= 8000].sum() / total

    geo_mean  = __import__('numpy').exp(__import__('numpy').mean(__import__('numpy').log(magnitude + 1e-9)))
    flatness  = float(geo_mean / (__import__('numpy').mean(magnitude) + 1e-9))
    centroid  = float(__import__('numpy').sum(freqs * magnitude) / total)
    zcr       = float(__import__('numpy').mean(__import__('numpy').abs(__import__('numpy').diff(__import__('numpy').sign(frame)))) / 2)

    if zcr > 0.25 and vhigh > 0.20:
        return "crash" if low + sub > 0.15 else "hihat_cl"
    if sub > 0.20 or (centroid < 400 and sub + low > 0.40):
        return "kick"
    if centroid < 900 and flatness < 0.15 and mid > 0.30:
        if centroid < 400:   return "tom_lo"
        elif centroid < 600: return "tom_mid"
        else:                return "tom_hi"
    return "snare"
