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
        onset_threshold=0.3,
        frame_threshold=0.2,
        minimum_note_length=30,
        melodia_trick=False,
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


def midi_to_tab(midi_path: str, output_dir: str) -> str:
    """MIDI → GuitarPro(.gp5) 타브 악보 생성."""
    import pretty_midi
    import guitarpro

    midi_path = Path(midi_path)
    output_dir = Path(output_dir)

    # 베이스 표준 튜닝 개방현 MIDI 음높이 (1현~4현: G2, D2, A1, E1)
    OPEN_STRINGS = [43, 38, 33, 28]
    MAX_FRET = 24
    SLOTS_PER_MEASURE = 16  # 4/4박자 × 1/16음표 고정 그리드

    midi = pretty_midi.PrettyMIDI(str(midi_path))
    tempo_times, tempos = midi.get_tempo_changes()
    bpm = float(tempos[0]) if len(tempos) > 0 else 120.0
    bpm = max(60.0, min(240.0, bpm))
    logger.info("midi_to_tab BPM: %.1f", bpm)

    all_notes = []
    for inst in midi.instruments:
        all_notes.extend(inst.notes)
    all_notes.sort(key=lambda n: n.start)

    if not all_notes:
        logger.warning("MIDI에 음표가 없습니다.")
        # 빈 악보 반환
        all_notes = []

    def best_position(pitch_val, prev_fret=None):
        candidates = []
        for i, open_pitch in enumerate(OPEN_STRINGS):
            fret = pitch_val - open_pitch
            if 0 <= fret <= MAX_FRET:
                cost = fret + (abs(fret - prev_fret) * 0.5 if prev_fret is not None else 0)
                candidates.append((cost, i + 1, fret))
        return min(candidates, default=(0, 1, 0))[1:]

    # 1/16음표 그리드에 음표를 배치 (슬롯당 하나, 벨로시티 최대값 우선)
    seconds_per_beat = 60.0 / bpm
    grid_sec = seconds_per_beat / 4  # 1/16음표 길이(초)

    slot_notes: dict[int, object] = {}
    for n in all_notes:
        slot = round(n.start / grid_sec)
        if slot not in slot_notes or n.velocity > slot_notes[slot].velocity:
            slot_notes[slot] = n

    max_slot = max(slot_notes.keys()) if slot_notes else 0
    num_measures = max(1, max_slot // SLOTS_PER_MEASURE + 1)

    # GuitarPro Song 구성
    # Song()/Track()이 기본으로 채워두는 measureHeader/measure 1개를 그대로 두면
    # 헤더-마디 개수가 어긋나 alphaTab이 파싱하지 못하므로 비우고 새로 채운다.
    song = guitarpro.Song()
    song.tempo = int(bpm)
    song.measureHeaders = []

    track = guitarpro.Track(song)
    track.name = "Bass"
    track.isBass = True
    track.strings = [
        guitarpro.GuitarString(1, 43),  # G2
        guitarpro.GuitarString(2, 38),  # D2
        guitarpro.GuitarString(3, 33),  # A1
        guitarpro.GuitarString(4, 28),  # E1
    ]
    track.channel.instrument = 33  # Electric Bass
    track.measures = []

    prev_fret = None

    for m in range(num_measures):
        header = guitarpro.MeasureHeader()
        header.number = m + 1
        header.timeSignature.numerator = 4
        header.timeSignature.denominator = guitarpro.Duration(value=4)
        song.measureHeaders.append(header)

        measure = guitarpro.Measure(track, header)
        voice = measure.voices[0]

        # 마디마다 정확히 SLOTS_PER_MEASURE(=16)개의 1/16음표 비트를 생성
        # alphaTab 임계값(100)을 절대 초과하지 않음
        for slot_in_measure in range(SLOTS_PER_MEASURE):
            global_slot = m * SLOTS_PER_MEASURE + slot_in_measure
            beat = guitarpro.Beat(voice)
            beat.duration = guitarpro.Duration(value=16)  # 1/16음표

            if global_slot in slot_notes:
                n = slot_notes[global_slot]
                string_num, fret = best_position(n.pitch, prev_fret)
                prev_fret = fret

                # Note()의 첫 위치 인자는 string이 아니라 beat이므로
                # string/type은 반드시 속성으로 직접 설정해야 한다.
                gp_note = guitarpro.Note(beat)
                gp_note.string = string_num
                gp_note.value = fret
                gp_note.type = guitarpro.NoteType.normal
                gp_note.velocity = min(127, max(1, getattr(n, 'velocity', 95)))
                beat.notes.append(gp_note)
                beat.status = guitarpro.BeatStatus.normal
            else:
                beat.status = guitarpro.BeatStatus.rest

            voice.beats.append(beat)

        track.measures.append(measure)

    song.tracks = [track]

    tab_path = output_dir / "bass_tab.gp5"
    guitarpro.write(song, str(tab_path))
    logger.info("GuitarPro 타브 저장: %s", tab_path)
    return str(tab_path)


def midi_to_musicxml(midi_path: str, output_dir: str) -> str:
    """MIDI → MusicXML 변환 (베이스 클레프 단일 보표)."""
    from music21 import converter, clef

    midi_path = Path(midi_path)
    output_dir = Path(output_dir)

    logger.info("MusicXML 변환 시작: %s", midi_path)

    score = converter.parse(str(midi_path))

    # 첫 파트에 베이스 클레프 적용
    for part in score.parts:
        measures = part.getElementsByClass('Measure')
        if measures:
            first_measure = measures[0]
            first_measure.clef = clef.BassClef()
        break

    xml_path = output_dir / "bass.musicxml"
    score.write("musicxml", fp=str(xml_path))
    logger.info("MusicXML 저장: %s (%d notes)", xml_path, len(list(score.flatten().notes)))

    return str(xml_path)
