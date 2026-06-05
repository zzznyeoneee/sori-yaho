"""
담당: 김진현
MIDI / MusicXML 파싱 + 오른손/왼손 파트 분리
"""
import copy
import functools

import pretty_midi
from music21 import converter as m21_converter
from music21 import stream, note, chord, instrument, key, meter


# ---------------------------------------------------------------------------
# Public API  (인터페이스 계약 — 시그니처 변경 금지)
# ---------------------------------------------------------------------------

def get_pretty_midi(midi_path: str) -> pretty_midi.PrettyMIDI:
    """
    MIDI 파싱. 무거운 작업이므로 캐싱 적용.
    반환값: pretty_midi.PrettyMIDI 객체
    """
    return _load_pretty_midi(midi_path)


def get_music21_score(xml_path: str) -> stream.Score:
    """
    MusicXML 파싱.
    반환값: music21.stream.Score 객체
    """
    return m21_converter.parse(xml_path)


def split_hands(score: stream.Score) -> tuple[stream.Part, stream.Part]:
    """
    악보를 오른손/왼손 파트로 분리.
    반환값: (right_hand_part, left_hand_part)
    타입:   (music21.stream.Part, music21.stream.Part)
    """
    parts = list(score.parts)

    if len(parts) == 0:
        return stream.Part(), stream.Part()

    # 조표·박자표는 첫 번째 파트에서 가져오고, 모든 음표를 합쳐 가온 도(C4) 기준으로 분리
    first_flat = parts[0].flatten()
    key_sigs = list(first_flat.getElementsByClass(key.KeySignature))
    time_sigs = list(first_flat.getElementsByClass(meter.TimeSignature))

    merged = stream.Part(id="merged")
    for ks in key_sigs:
        merged.insert(ks.offset, copy.deepcopy(ks))
    for ts in time_sigs:
        merged.insert(ts.offset, copy.deepcopy(ts)) 
    for part in parts:
        for element in part.flatten().notesAndRests:
            merged.insert(element.offset, copy.deepcopy(element))

    return _split_by_pitch(merged)


# ---------------------------------------------------------------------------
# 내부 구현
# ---------------------------------------------------------------------------

_SPLIT_POINT = 60  # C4 기준 — 이상이면 오른손, 미만이면 왼손


@functools.lru_cache(maxsize=32)
def _load_pretty_midi(midi_path: str) -> pretty_midi.PrettyMIDI:
    return pretty_midi.PrettyMIDI(midi_path)


def _split_by_pitch(part: stream.Part) -> tuple[stream.Part, stream.Part]:
    """
    단일 파트의 음표를 C4(MIDI 60) 기준으로 오른손/왼손으로 분리.
    화음(Chord) 내 음표도 개별 피치 기준으로 배분.
    """
    rh = stream.Part(id="RH")
    lh = stream.Part(id="LH")
    piano_rh = instrument.Piano()
    piano_rh.partName = ""
    piano_rh.partAbbreviation = ""
    piano_rh.instrumentName = ""
    piano_rh.instrumentAbbreviation = ""
    rh.insert(0, piano_rh)
    piano_lh = instrument.Piano()
    piano_lh.partName = ""
    piano_lh.partAbbreviation = ""
    piano_lh.instrumentName = ""
    piano_lh.instrumentAbbreviation = ""
    lh.insert(0, piano_lh)

    flat = part.flatten()
    for ks in flat.getElementsByClass(key.KeySignature):
        rh.insert(ks.offset, copy.deepcopy(ks))
        lh.insert(ks.offset, copy.deepcopy(ks))
    for ts in flat.getElementsByClass(meter.TimeSignature):
        rh.insert(ts.offset, copy.deepcopy(ts))
        lh.insert(ts.offset, copy.deepcopy(ts))

    for element in flat.notesAndRests:
        offset = element.offset

        if isinstance(element, note.Rest):
            rh.insert(offset, element)
            lh.insert(offset, element)
            continue

        if isinstance(element, note.Note):
            if element.pitch.midi >= _SPLIT_POINT:
                rh.insert(offset, element)
            else:
                lh.insert(offset, element)
            continue

        if isinstance(element, chord.Chord):
            rh_pitches = [p for p in element.pitches if p.midi >= _SPLIT_POINT]
            lh_pitches = [p for p in element.pitches if p.midi < _SPLIT_POINT]

            if rh_pitches:
                rh_chord = chord.Chord(rh_pitches)
                rh_chord.duration = element.duration
                rh.insert(offset, rh_chord)

            if lh_pitches:
                lh_chord = chord.Chord(lh_pitches)
                lh_chord.duration = element.duration
                lh.insert(offset, lh_chord)

    return rh, lh
