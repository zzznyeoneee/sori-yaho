"""
Basic Pitch adapter — Spotify ICASSP 2022 / NMP 모델.

piano_transcription_inference 와 동일한 계약:
  transcribe_basic_pitch(wav_path) → pretty_midi.PrettyMIDI

기존 파이프라인(_beat_quantize, clean_midi, _classify_voices)과
완전히 호환되도록 설계. Basic Pitch가 설치되지 않은 경우
ImportError를 명시적 메시지와 함께 raise.

설치:
    pip install basic-pitch
    또는
    pip install -e ".[basic_pitch]"
"""
from __future__ import annotations


def transcribe_basic_pitch(
    wav_path: str,
    onset_threshold: float = 0.5,
    frame_threshold: float = 0.3,
    minimum_note_length: float = 127.7,
) -> "pretty_midi.PrettyMIDI":
    """
    Basic Pitch (Spotify) 로 WAV → 폴리포닉 pretty_midi.PrettyMIDI.

    Parameters
    ----------
    wav_path          : 입력 WAV 파일 경로.
    onset_threshold   : onset 감지 임계값 (0–1). 높을수록 noise 감소.
    frame_threshold   : frame-level pitch 임계값 (0–1).
    minimum_note_length: 최소 음표 길이(ms). 120bpm 16분음표 ≈ 125ms.

    Returns
    -------
    pretty_midi.PrettyMIDI — 폴리포닉 채보 결과.

    Notes
    -----
    - Basic Pitch는 PrettyMIDI tempo를 항상 120으로 설정.
      이후 _beat_quantize()는 librosa-detected bpm을 직접 사용하므로
      이 tempo 값은 파이프라인에 영향을 주지 않는다.
    - melodia_trick=True: 선율 우선 추출로 ghost note 감소.
    - 주파수 범위는 피아노 음역(A0–C8)으로 고정.
    """
    try:
        from basic_pitch.inference import predict as bp_predict
        from basic_pitch import ICASSP_2022_MODEL_PATH
    except ImportError as exc:
        raise ImportError(
            "basic-pitch 패키지가 설치되지 않았습니다.\n"
            "설치: pip install basic-pitch\n"
            "또는: pip install -e \".[basic_pitch]\""
        ) from exc

    try:
        import librosa
    except ImportError as exc:
        raise ImportError("librosa가 필요합니다: pip install librosa") from exc

    fmin = librosa.note_to_hz("A0")   # 27.5 Hz  (피아노 최저음)
    fmax = librosa.note_to_hz("C8")   # 4186 Hz (피아노 최고음)

    _model_output, midi_data, _note_events = bp_predict(
        audio_path=wav_path,
        model_or_model_path=ICASSP_2022_MODEL_PATH,
        onset_threshold=onset_threshold,
        frame_threshold=frame_threshold,
        minimum_note_length=minimum_note_length,
        minimum_frequency=fmin,
        maximum_frequency=fmax,
        multiple_pitch_bends=False,
        melodia_trick=True,
    )

    # bp_predict 는 (dict, PrettyMIDI, list) 튜플 반환
    return midi_data
