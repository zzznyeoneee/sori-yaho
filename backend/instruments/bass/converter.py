"""Bass audio → MIDI → MusicXML 변환 파이프라인."""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# 베이스 음역대: E1(28) ~ G3(55)
BASS_PITCH_MIN = 28
BASS_PITCH_MAX = 55


def audio_to_midi(audio_path: str, output_dir: str) -> str:
    """Basic Pitch로 베이스 WAV → MIDI 변환."""
    from basic_pitch.inference import predict, Model
    from basic_pitch import ICASSP_2022_MODEL_PATH
    import pretty_midi

    audio_path = Path(audio_path)
    output_dir = Path(output_dir)

    logger.info("Basic Pitch 베이스 채보 시작: %s", audio_path)

    model = Model(ICASSP_2022_MODEL_PATH)

    model_output, midi_data, note_events = predict(
        str(audio_path),
        model,
        onset_threshold=0.5,
        frame_threshold=0.3,
        minimum_note_length=58,
        minimum_frequency=40.0,
        maximum_frequency=200.0,
        melodia_trick=True,
    )

    # 베이스 음역대 밖 음표 제거
    bass_midi = pretty_midi.PrettyMIDI(initial_tempo=midi_data.estimate_tempo())
    instrument = pretty_midi.Instrument(program=33, name="Bass")  # Electric Bass
    for inst in midi_data.instruments:
        for note in inst.notes:
            if BASS_PITCH_MIN <= note.pitch <= BASS_PITCH_MAX:
                instrument.notes.append(note)

    instrument.notes.sort(key=lambda n: n.start)
    bass_midi.instruments.append(instrument)

    midi_path = output_dir / "bass.mid"
    bass_midi.write(str(midi_path))
    logger.info("MIDI 저장: %s", midi_path)

    return str(midi_path)


def midi_to_musicxml(midi_path: str, output_dir: str) -> str:
    """MIDI → MusicXML 변환 (베이스 클레프 단일 보표)."""
    import music21.midi.translate as m21midi
    from music21 import converter, stream, clef, tempo, meter, key
    from music21.midi import MidiFile

    midi_path = Path(midi_path)
    output_dir = Path(output_dir)

    logger.info("MusicXML 변환 시작: %s", midi_path)

    score = converter.parse(str(midi_path))

    # 단일 파트로 합치고 베이스 클레프 적용
    flat = score.flat.notes.stream()
    part = stream.Part()
    part.id = "Bass"

    m = stream.Measure(number=1)
    m.append(clef.BassClef())
    m.append(meter.TimeSignature("4/4"))
    m.append(key.KeySignature(0))

    bpm = 120
    try:
        bpm_marks = score.flat.getElementsByClass(tempo.MetronomeMark)
        if bpm_marks:
            bpm = int(bpm_marks[0].number)
    except Exception:
        pass
    m.append(tempo.MetronomeMark(number=bpm))
    part.append(m)

    for el in flat:
        part.append(el)

    out_score = stream.Score()
    out_score.append(part)
    out_score.makeNotation(inPlace=True)

    xml_path = output_dir / "bass.musicxml"
    out_score.write("musicxml", fp=str(xml_path))
    logger.info("MusicXML 저장: %s", xml_path)

    return str(xml_path)
