"""Vocal audio → MIDI → MusicXML 변환 파이프라인."""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# 보컬 음역대: C2(36) ~ C6(84) — 저음 남성부터 고음 여성까지 포괄
VOCAL_PITCH_MIN = 36
VOCAL_PITCH_MAX = 84


def audio_to_midi(audio_path: str, output_dir: str) -> str:
    """Basic Pitch로 보컬 WAV → MIDI 변환."""
    from basic_pitch.inference import predict, Model
    from basic_pitch import ICASSP_2022_MODEL_PATH
    import pretty_midi

    audio_path = Path(audio_path)
    output_dir = Path(output_dir)

    logger.info("Basic Pitch 보컬 채보 시작: %s", audio_path)

    model = Model(ICASSP_2022_MODEL_PATH)

    # melodia_trick=True: 단선율(monophonic) 보컬 멜로디 추출에 적합
    # (basic_pitch가 공식적으로 권장하는 리드 보컬/멜로디 설정)
    model_output, midi_data, note_events = predict(
        str(audio_path),
        model,
        onset_threshold=0.5,
        frame_threshold=0.3,
        minimum_note_length=58,
        melodia_trick=True,
    )

    # 보컬 음역대 밖 음표 제거
    vocal_midi = pretty_midi.PrettyMIDI(initial_tempo=midi_data.estimate_tempo())
    instrument = pretty_midi.Instrument(program=52, name="Vocal")  # Choir Aahs
    for inst in midi_data.instruments:
        for note in inst.notes:
            if VOCAL_PITCH_MIN <= note.pitch <= VOCAL_PITCH_MAX:
                instrument.notes.append(note)

    instrument.notes.sort(key=lambda n: n.start)
    vocal_midi.instruments.append(instrument)

    midi_path = output_dir / "vocal.mid"
    vocal_midi.write(str(midi_path))
    logger.info("MIDI 저장: %s", midi_path)

    return str(midi_path)


def midi_to_musicxml(midi_path: str, output_dir: str) -> str:
    """MIDI → MusicXML 변환 (보컬 높은음자리표 단일 보표)."""
    from music21 import converter, clef

    midi_path = Path(midi_path)
    output_dir = Path(output_dir)

    logger.info("MusicXML 변환 시작: %s", midi_path)

    score = converter.parse(str(midi_path))

    # 첫 파트에 높은음자리표 적용
    for part in score.parts:
        measures = part.getElementsByClass('Measure')
        if measures:
            first_measure = measures[0]
            first_measure.clef = clef.TrebleClef()
        break

    xml_path = output_dir / "vocal.musicxml"
    score.write("musicxml", fp=str(xml_path))
    logger.info("MusicXML 저장: %s (%d notes)", xml_path, len(list(score.flatten().notes)))

    return str(xml_path)
