"""Convert drum MIDI to MusicXML notation with proper percussion staff."""
import pretty_midi
from fractions import Fraction
from pathlib import Path
from music21 import (
    stream, note, chord, meter, tempo as m21tempo,
    clef, instrument as m21instrument, pitch as m21pitch, layout,
)
from music21.note import NotRest


# GM drum pitch → (staff step, octave, notehead type, stem direction)
# treble clef 기준 위치:
#   lines(아래→위): E4 G4 B4 D5 F5
#   spaces: F4 A4 C5 E5
_DRUM_NOTATION = {
    35: ("F",  4, "normal",  "down"),   # acoustic bass drum (kick)
    36: ("F",  4, "normal",  "down"),   # bass drum 1 (kick)
    38: ("B",  4, "normal",  "up"),     # snare
    40: ("B",  4, "normal",  "up"),     # electric snare
    37: ("C",  5, "x",       "up"),     # side stick
    42: ("E",  5, "x",       "up"),     # hihat closed
    44: ("E",  5, "x",       "up"),     # hihat pedal
    46: ("F",  5, "x",       "up"),     # hihat open
    49: ("A",  5, "x",       "up"),     # crash 1
    57: ("A",  5, "x",       "up"),     # crash 2
    51: ("G",  5, "x",       "up"),     # ride 1
    59: ("G",  5, "x",       "up"),     # ride 2
    53: ("G",  5, "x",       "up"),     # ride bell
    48: ("D",  5, "normal",  "up"),     # hi tom
    50: ("D",  5, "normal",  "up"),     # hi-mid tom
    45: ("A",  4, "normal",  "up"),     # mid tom
    47: ("A",  4, "normal",  "up"),     # low-mid tom
    41: ("G",  4, "normal",  "up"),     # low tom
    43: ("G",  4, "normal",  "up"),     # high floor tom
}
_DEFAULT_NOTATION = ("B", 4, "normal", "up")


def _make_note(pitch_num: int, duration_ql: float) -> note.Note:
    step, octave, head, stem = _DRUM_NOTATION.get(pitch_num, _DEFAULT_NOTATION)
    n = note.Note()
    n.pitch.step = step
    n.pitch.octave = octave
    n.pitch.accidental = None
    n.duration.quarterLength = max(duration_ql, 0.125)
    n.notehead = head
    n.stemDirection = stem
    return n


def _snap_ql(ql: float) -> float:
    """최소 단위(32분음표=0.125)에 스냅."""
    grid = 0.125
    snapped = round(ql / grid) * grid
    return max(snapped, grid)


def midi_to_drum_score(midi_path: str, output_dir: str) -> str:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    pm = pretty_midi.PrettyMIDI(midi_path)
    bpm = pm.estimate_tempo()

    # 박자 정보
    beat_ql = 1.0          # 4/4 기준 quarter = 1 ql
    measure_ql = 4.0

    score = stream.Score()
    part = stream.Part()
    sl = layout.StaffLayout()
    sl.staffLines = 5
    part.insert(0, sl)
    part.insert(0, m21instrument.Percussion())
    part.insert(0, clef.PercussionClef())
    part.insert(0, meter.TimeSignature("4/4"))
    part.insert(0, m21tempo.MetronomeMark(number=int(bpm)))

    # 드럼 채널 노트 수집
    import logging
    logger = logging.getLogger(__name__)
    all_notes = []
    for inst in pm.instruments:
        if inst.is_drum:
            for n in inst.notes:
                all_notes.append(n)
    all_notes.sort(key=lambda n: n.start)
    pitch_counts = {}
    for n in all_notes:
        pitch_counts[n.pitch] = pitch_counts.get(n.pitch, 0) + 1
    logger.info("drum pitches: %s", sorted(pitch_counts.items()))

    if not all_notes:
        score.append(part)
        out_path = output_dir / f"{Path(midi_path).stem}.xml"
        score.write("musicxml", fp=str(out_path))
        return str(out_path)

    # 초 → quarterLength 변환
    sec_per_beat = 60.0 / bpm

    def sec_to_ql(t: float) -> float:
        return t / sec_per_beat

    total_ql = sec_to_ql(all_notes[-1].end) + measure_ql
    n_measures = max(1, int(total_ql / measure_ql) + 1)

    # 마디별 버킷
    measures: list[list] = [[] for _ in range(n_measures)]
    for pn in all_notes:
        onset_ql = sec_to_ql(pn.start)
        dur_ql = _snap_ql(sec_to_ql(pn.end - pn.start))
        m_idx = int(onset_ql / measure_ql)
        if m_idx >= n_measures:
            m_idx = n_measures - 1
        pos_in_measure = _snap_ql(onset_ql - m_idx * measure_ql)
        measures[m_idx].append((pos_in_measure, pn.pitch, dur_ql))

    for m_idx, events in enumerate(measures):
        m = stream.Measure(number=m_idx + 1)

        if not events:
            r = note.Rest()
            r.duration.quarterLength = measure_ql
            m.append(r)
            part.append(m)
            continue

        # 같은 onset 묶기 → chord
        from collections import defaultdict
        by_pos: dict[float, list] = defaultdict(list)
        by_dur: dict[float, float] = {}
        for pos, pitch_num, dur in events:
            by_pos[pos].append(pitch_num)
            by_dur[pos] = max(by_dur.get(pos, 0.0), dur)

        positions = sorted(by_pos.keys())

        cursor = 0.0
        for pos in positions:
            # 이전 위치까지 rest 채우기
            if pos > cursor + 0.01:
                gap = _snap_ql(pos - cursor)
                r = note.Rest()
                r.duration.quarterLength = gap
                m.append(r)
                cursor += gap

            pitches = by_pos[pos]
            dur = by_dur[pos]

            if len(pitches) == 1:
                n21 = _make_note(pitches[0], dur)
                m.append(n21)
            else:
                notes_list = [_make_note(p, dur) for p in pitches]
                c = chord.Chord(notes_list)
                c.duration.quarterLength = dur
                m.append(c)
            cursor = pos + dur

        # 마디 끝까지 rest
        remaining = _snap_ql(measure_ql - cursor) if measure_ql - cursor > 0.01 else 0
        if remaining > 0:
            r = note.Rest()
            r.duration.quarterLength = remaining
            m.append(r)

        part.append(m)

    score.append(part)
    out_path = output_dir / f"{Path(midi_path).stem}.xml"
    score.write("musicxml", fp=str(out_path))

    # OSMD는 percussion clef를 단선보로 강제 렌더링하므로
    # treble clef로 교체하고 5선보 명시
    import re
    xml_text = out_path.read_text(encoding="utf-8")
    # staff-lines 5로 설정
    if "<staff-details>" in xml_text:
        xml_text = re.sub(r"<staff-lines>\d+</staff-lines>", "<staff-lines>5</staff-lines>", xml_text)
    else:
        xml_text = xml_text.replace(
            "<clef>",
            "<staff-details><staff-lines>5</staff-lines></staff-details><clef>",
            1,
        )
    # percussion clef → treble clef
    xml_text = re.sub(
        r"<clef>\s*<sign>percussion</sign>\s*</clef>",
        "<clef><sign>G</sign><line>2</line></clef>",
        xml_text,
    )
    out_path.write_text(xml_text, encoding="utf-8")

    return str(out_path)
