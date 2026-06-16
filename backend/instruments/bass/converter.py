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
    from fractions import Fraction

    midi_path = Path(midi_path)
    output_dir = Path(output_dir)

    # 베이스 표준 튜닝 개방현 MIDI 음높이 (1현~4현: G2, D2, A1, E1)
    OPEN_STRINGS = [43, 38, 33, 28]
    MAX_FRET = 24

    midi = pretty_midi.PrettyMIDI(str(midi_path))
    # 템포 이벤트에서 BPM 읽기 (없으면 120 기본값)
    # estimate_tempo()가 이상한 값을 반환할 수 있으므로 합리적인 범위로 클램프
    tempo_times, tempos = midi.get_tempo_changes()
    bpm = float(tempos[0]) if len(tempos) > 0 else 120.0
    bpm = max(60.0, min(240.0, bpm))
    logger.info("midi_to_tab BPM: %.1f", bpm)
    all_notes = []
    for inst in midi.instruments:
        all_notes.extend(inst.notes)
    all_notes.sort(key=lambda n: n.start)

    def best_position(pitch_val, prev_fret=None):
        candidates = []
        for i, open_pitch in enumerate(OPEN_STRINGS):
            fret = pitch_val - open_pitch
            if 0 <= fret <= MAX_FRET:
                cost = fret + (abs(fret - prev_fret) * 0.5 if prev_fret is not None else 0)
                candidates.append((cost, i + 1, fret))  # 1-indexed string
        return min(candidates, default=(0, 1, 0))[1:]

    # GuitarPro Song 구성
    song = guitarpro.Song()
    song.tempo = int(bpm)

    # 베이스 트랙 (song을 인자로 전달)
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

    beats_per_measure = 4
    seconds_per_beat = 60.0 / bpm
    seconds_per_measure = seconds_per_beat * beats_per_measure
    # 4/4박자에서 1/16음표 기준 최대 비트 수 (알파탭 임계값 100 이하로 유지)
    MAX_BEATS_PER_MEASURE = beats_per_measure * 16  # = 64

    # 음표를 마디별로 그룹화
    max_time = all_notes[-1].end if all_notes else 0
    num_measures = max(1, int(max_time / seconds_per_measure) + 1)

    prev_fret = None
    note_idx = 0

    for m in range(num_measures):
        measure_start = m * seconds_per_measure
        measure_end = measure_start + seconds_per_measure

        header = song.measureHeaders[m] if m < len(song.measureHeaders) else guitarpro.MeasureHeader()
        header.number = m + 1
        header.timeSignature.numerator = beats_per_measure
        header.timeSignature.denominator = guitarpro.Duration(value=4)
        if m >= len(song.measureHeaders):
            song.measureHeaders.append(header)

        measure = guitarpro.Measure(track, header)
        voice = measure.voices[0]

        # 이 마디에 속하는 음표 수집
        measure_notes = []
        while note_idx < len(all_notes) and all_notes[note_idx].start < measure_end:
            n = all_notes[note_idx]
            if n.start >= measure_start:
                measure_notes.append(n)
            note_idx += 1

        if not measure_notes:
            # 쉼표 박자 채우기
            beat = guitarpro.Beat(voice)
            beat.duration = guitarpro.Duration(value=1)
            beat.status = guitarpro.BeatStatus.rest
            voice.beats.append(beat)
        else:
            for n in measure_notes:
                # 마디 비트 수 초과 방지 (alphaTab 임계값 100 이하)
                if len(voice.beats) >= MAX_BEATS_PER_MEASURE:
                    break

                duration_sec = n.end - n.start
                duration_beats = duration_sec / seconds_per_beat
                # 가장 가까운 음표값 매핑 (최소 1/16음표)
                dur_map = [(4, 1), (2, 2), (1, 4), (0.5, 8), (0.25, 16)]
                value = min(dur_map, key=lambda x: abs(x[0] - duration_beats))[1]

                string_num, fret = best_position(n.pitch, prev_fret)
                prev_fret = fret

                gp_note = guitarpro.Note(string_num)
                gp_note.value = fret
                gp_note.velocity = min(127, max(1, n.velocity if hasattr(n, 'velocity') else 95))

                beat = guitarpro.Beat(voice)
                beat.duration = guitarpro.Duration(value=value)
                beat.notes.append(gp_note)
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
