"""Drum transcription with multi-class spectral classifier."""
import numpy as np
import pretty_midi
from pathlib import Path

# GM drum map
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


def _classify_onset(y: np.ndarray, sr: int, onset_sample: int, frame_len: int = 2048) -> str:
    """
    스펙트럼 특성으로 5종 드럼 분류:
    kick / snare / hihat_cl / crash / tom
    """
    frame = y[onset_sample: onset_sample + frame_len]
    if len(frame) < frame_len:
        frame = np.pad(frame, (0, frame_len - len(frame)))

    magnitude = np.abs(np.fft.rfft(frame))
    freqs = np.fft.rfftfreq(frame_len, d=1.0 / sr)
    total = magnitude.sum() + 1e-9

    # 주파수 대역 에너지 비율
    sub    = magnitude[freqs <   80].sum() / total   # 킥 서브베이스
    low    = magnitude[(freqs >= 80)  & (freqs < 300)].sum() / total
    mid    = magnitude[(freqs >= 300) & (freqs < 3000)].sum() / total
    high   = magnitude[(freqs >= 3000) & (freqs < 8000)].sum() / total
    vhigh  = magnitude[freqs >= 8000].sum() / total

    # 스펙트럴 센트로이드 (Hz)
    centroid = float(np.sum(freqs * magnitude) / total)

    # 스펙트럴 플랫니스 (1에 가까울수록 노이즈)
    geo_mean = np.exp(np.mean(np.log(magnitude + 1e-9)))
    arith_mean = np.mean(magnitude) + 1e-9
    flatness = geo_mean / arith_mean

    # 제로 크로싱 레이트 (높으면 하이햇/심벌)
    zcr = float(np.mean(np.abs(np.diff(np.sign(frame)))) / 2)

    # --- 분류 규칙 ---
    # 하이햇/심벌: 매우 높은 ZCR + 고역 에너지
    if zcr > 0.25 and vhigh > 0.20:
        # 크래시: 서스테인이 길고 저역도 있음
        if low + sub > 0.15:
            return "crash"
        return "hihat_cl"

    # 킥: 서브베이스 에너지 강함 + 낮은 센트로이드
    if sub > 0.20 or (centroid < 400 and sub + low > 0.40):
        return "kick"

    # 탐탐: 킥보다 센트로이드 높고 플랫니스 낮음 (tonal)
    if centroid < 900 and flatness < 0.15 and mid > 0.30:
        if centroid < 400:
            return "tom_lo"
        elif centroid < 600:
            return "tom_mid"
        else:
            return "tom_hi"

    # 스네어: 넓은 대역 노이즈
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
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    bpm = float(round(np.atleast_1d(tempo)[0]))

    onset_times   = librosa.onset.onset_detect(y=y, sr=sr, units="time",
                                                delta=0.07, wait=4)
    onset_samples = librosa.onset.onset_detect(y=y, sr=sr, units="samples",
                                                delta=0.07, wait=4)

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
