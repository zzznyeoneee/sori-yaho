"""
담당: 김진현

오디오 → MIDI → MusicXML 변환 파이프라인

[채보 전략]
  오른손 (선율):  librosa.pyin — Probabilistic YIN 단음 선율 추출
                 → 가장 깨끗한 멜로디 라인. 공명·배음 완전 제거.

  왼손 (반주):   piano_transcription_inference (Kong et al., ICASSP 2021)
                 — 폴리포닉 채보 모델로 베이스/반주 음표 추출.
                 → onset_threshold=0.5 로 ghost note 최소화.

  조합 로직:
    1) pyin 으로 선율 피치 궤적 추출
    2) piano_transcription_inference 전체 채보 → beat-aligned 퀀타이즈 → 후처리
    3) 각 후처리 음표를 "선율 후보(pyin 피치 ±3반음)"와 "베이스(<split_pitch)"로 분류
    4) 오른손 = 선율 + 선율 인근 화음(최대 3음), 왼손 = 베이스
    5) 동일 오프셋의 오른손 음표가 없는 경우 선율 음표로 채움

[음원 분리]
  Défossez et al., "Hybrid Transformers for Music Source Separation",
  ICASSP 2023.  (htdemucs_6s 모델)

[Beat Tracking]
  McFee et al., "librosa: Audio and Music Signal Analysis in Python",
  SciPy 2015.
"""
from __future__ import annotations

import random
import subprocess
import sys
from collections import defaultdict, Counter
from fractions import Fraction
from pathlib import Path

import numpy as np
from music21 import (
    converter as m21_converter,
    stream, instrument, clef,
    note as m21_note, chord as m21_chord,
    meter as m21_meter, tempo as m21_tempo,
    key as m21_key,
)

from instruments.piano.post_process import clean_midi, PRESETS


def _get_musescore_path() -> str:
    if settings.MUSESCORE_PATH:
        return settings.MUSESCORE_PATH
    if sys.platform == "win32":
        return r"C:\Program Files\MuseScore 4\bin\MuseScore4.exe"
    elif sys.platform == "darwin":
        return "/Applications/MuseScore 4.app/Contents/MacOS/mscore"
    return "mscore"


# ---------------------------------------------------------------------------
# 상수
# ---------------------------------------------------------------------------
_DEMUCS_MODEL       = "htdemucs_6s"
_PIANO_STEM         = "piano"
_QL_GRID            = 0.25          # 16분음표 quarter-length
_MEASURE_QL         = 4.0           # 4/4 박자 = 4 QL
_MAX_RH_CHORD       = 4             # 오른손: 최대 4음
_MAX_LH_CHORD       = 4             # 왼손: 최대 4음
_N_DIV              = 4             # beat 당 subdivision 수 (= 16분음표)
_MELODY_TOLERANCE   = 2             # pyin 피치 ±2반음 허용 (더 엄격한 선율 매칭)

# 표준 음가 (이진 그리드만 — 초기 버전은 triplet·점음표 미지원)
# 이진값만 허용해야 music21이 tuplet 없이 깔끔한 악보를 생성한다.
# triplet을 허용하면 같은 마디에 binary(1/4)·triplet(1/3)이 섞여
# music21이 LCM인 12-tuplet을 만들어 악보가 붕괴된다.
#
# 점음표(0.75, 1.5, 3.0)도 제외: 점음표 뒤 쉬표가 비-그리드 위치에 생겨
# music21 beam/rest 배치가 어긋나는 문제를 사전 차단.
_STD_QL: tuple[float, ...] = (
    0.25,   # 16분음표
    0.5,    # 8분음표
    1.0,    # 4분음표
    2.0,    # 2분음표
    4.0,    # 온음표
)

# ---------------------------------------------------------------------------
# 조성 감지
# ---------------------------------------------------------------------------

def _detect_key(notes: "list[tuple[float, int, float]]") -> "m21_key.Key":
    """
    음표 목록 (offset, midi_pitch, ql) 에서 조성을 자동 감지.

    music21 Krumhansl-Schmuckler 알고리즘 사용.
    감지 실패 시 C major fallback.
    """
    try:
        tmp = stream.Stream()
        for _, midi_p, ql in notes[:400]:   # 최대 400개 샘플
            n = m21_note.Note()
            n.pitch.midi  = midi_p
            n.quarterLength = max(ql, _QL_GRID)
            tmp.append(n)
        detected = tmp.analyze("key")
        return detected
    except Exception:
        return m21_key.Key("C")


# ---------------------------------------------------------------------------
# Public API  (시그니처 변경 금지)
# ---------------------------------------------------------------------------

def audio_to_midi(audio_path: str, output_dir: str, progress_cb=None) -> str:
    """audio(.mp3/.wav) → piano stem(Demucs) → MIDI"""
    if progress_cb:
        progress_cb(3)
    piano_wav = _separate_piano(audio_path, output_dir, progress_cb=progress_cb)
    if progress_cb:
        progress_cb(30)   # Demucs 완료
    return _transcribe(piano_wav, output_dir, progress_cb=progress_cb)


def midi_to_musicxml(midi_path: str, output_dir: str) -> str:
    """MIDI → MusicXML  (4/4 강제 + 조성 자동 감지 + 손 분리 + 쉼표 자동 채우기)"""
    out   = Path(output_dir) / (Path(midi_path).stem + ".xml")
    score = m21_converter.parse(midi_path)

    mm_list = list(score.flatten().getElementsByClass("MetronomeMark"))
    bpm     = float(mm_list[0].number) if mm_list else 120.0

    grand_staff = _split_hands(score, bpm)

    # makeNotation=False: build_part() 에서 이미 makeBeams, makeAccidentals,
    # makeRests 를 직접 호출했으므로 write 시 재처리하지 않는다.
    # (재처리 시 makeAccidentals 가 key signature 를 무시하고 모든 임시표를 재추가할 수 있음)
    grand_staff.write("musicxml", fp=str(out))
    return str(out)


def musicxml_to_midi(xml_path: str, output_dir: str) -> str:
    """MusicXML → MIDI  (재생용, 템포 레퍼런트 보정 포함)"""
    from music21 import duration as m21_duration

    out   = Path(output_dir) / "original.mid"
    score = m21_converter.parse(xml_path)

    for mm in score.flatten().getElementsByClass("MetronomeMark"):
        ref_ql = getattr(mm.referent, "quarterLength", 1.0)
        if abs(ref_ql - 1.0) > 0.01:
            mm.number   = round(mm.number * ref_ql, 4)
            mm.referent = m21_duration.Duration(1.0)

    score.write("midi", fp=str(out))
    return str(out)


# ---------------------------------------------------------------------------
# 내부 헬퍼: 공통
# ---------------------------------------------------------------------------

def _q(val: float) -> float:
    """quarter-length 값을 16분음표(0.25 QL) 그리드로 반올림."""
    return round(val / _QL_GRID) * _QL_GRID

_SPLIT_PITCH = 60

def _fix_staff_assignment(xml_path: str) -> None:
    """음표 피치 기준으로 staff 번호와 clef를 함께 수정.
    C4(MIDI 60) 이상 → staff 1(높은음자리표), 미만 → staff 2(낮은음자리표)
    """
    import xml.etree.ElementTree as ET
    STEPS = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}

    tree = ET.parse(xml_path)
    root = tree.getroot()
    ns = root.tag.split('}')[0].lstrip('{') if '}' in root.tag else ''
    tag = lambda t: f'{{{ns}}}{t}' if ns else t

    for note_el in root.iter(tag('note')):
        step_el = note_el.find(f'{tag("pitch")}/{tag("step")}')
        octave_el = note_el.find(f'{tag("pitch")}/{tag("octave")}')
        staff_el = note_el.find(tag('staff'))
        if step_el is None or octave_el is None or staff_el is None:
            continue
        midi = STEPS.get(step_el.text, 0) + (int(octave_el.text) + 1) * 12
        staff_el.text = '1' if midi >= _SPLIT_PITCH else '2'

    # clef도 함께 수정
    parts = list(root.iter(tag('part')))
    if len(parts) == 1:
        for clef_el in parts[0].iter(tag('clef')):
            number = clef_el.get('number', '1')
            sign, line = ('G', '2') if number == '1' else ('F', '4')
            sign_el = clef_el.find(tag('sign'))
            line_el = clef_el.find(tag('line'))
            if sign_el is not None:
                sign_el.text = sign
            if line_el is not None:
                line_el.text = line
    else:
        for i, part in enumerate(parts[:2]):
            sign, line = ('G', '2') if i == 0 else ('F', '4')
            for clef_el in part.iter(tag('clef')):
                sign_el = clef_el.find(tag('sign'))
                line_el = clef_el.find(tag('line'))
                if sign_el is not None:
                    sign_el.text = sign
                if line_el is not None:
                    line_el.text = line

    tree.write(xml_path, xml_declaration=True, encoding='unicode')

def _fix_clefs(xml_path: str) -> None:
    """MuseScore 변환 후 스태프 번호 기준으로 음자리표를 고정 배정.
    number=1 → 높은음자리표, number=2 → 낮은음자리표
    단일 파트 두 스태프 및 두 파트 모두 처리.
    """
    import xml.etree.ElementTree as ET

    tree = ET.parse(xml_path)
    root = tree.getroot()
    ns = root.tag.split('}')[0].lstrip('{') if '}' in root.tag else ''
    tag = lambda t: f'{{{ns}}}{t}' if ns else t

    parts = list(root.iter(tag('part')))
    modified = False

    if len(parts) == 1:
        # 단일 파트, 두 스태프: clef number 속성으로 구분
        for clef_el in parts[0].iter(tag('clef')):
            number = clef_el.get('number', '1')
            sign, line = ('G', '2') if number == '1' else ('F', '4')
            sign_el = clef_el.find(tag('sign'))
            line_el = clef_el.find(tag('line'))
            if sign_el is not None:
                sign_el.text = sign
            if line_el is not None:
                line_el.text = line
            modified = True
    else:
        # 두 파트: 파트 순서로 구분
        for i, part in enumerate(parts[:2]):
            sign, line = ('G', '2') if i == 0 else ('F', '4')
            for clef_el in part.iter(tag('clef')):
                sign_el = clef_el.find(tag('sign'))
                line_el = clef_el.find(tag('line'))
                if sign_el is not None:
                    sign_el.text = sign
                if line_el is not None:
                    line_el.text = line
                modified = True

    if modified:
        tree.write(xml_path, xml_declaration=True, encoding='unicode')

def _snap_ql(ql: float) -> float:
    """quarter-length를 가장 가까운 표준 음가로 스냅 (이진 + 셋잇단 포함)."""
    if ql <= 0:
        return _QL_GRID
    return min(_STD_QL, key=lambda x: abs(x - ql))


def _smart_q(val: float) -> float:
    """quarter-length 값을 16분음표(0.25 QL) 이진 그리드로 반올림.

    초기 버전은 triplet 미지원 — 항상 binary grid만 사용.
    triplet 그리드(1/3, 2/3 등)를 혼용하면 music21이 12-tuplet을 생성하므로
    이진값으로만 스냅한다.
    """
    return round(val / _QL_GRID) * _QL_GRID


# 셋잇단음 QL → 정확한 Fraction 매핑 (music21 tuplet 표기용)
_FRAC_MAP: dict[int, Fraction] = {1: Fraction(1, 3), 2: Fraction(2, 3), 4: Fraction(4, 3)}


def _to_frac_if_triplet(ql: float):
    """QL이 셋잇단음 값(1/3, 2/3, 4/3)에 가까우면 Fraction 반환, 아니면 float."""
    n = round(ql * 3)
    if n in _FRAC_MAP and abs(n / 3 - ql) < 0.02:
        return _FRAC_MAP[n]
    return ql


def _make_note(pitch_midi: int, ql: float) -> m21_note.Note:
    """피치·음가만으로 구성된 깨끗한 Note 객체."""
    n = m21_note.Note()
    n.pitch.midi   = pitch_midi
    n.quarterLength = ql
    return n

def _calc_split_pitch(midi: "pretty_midi.PrettyMIDI") -> int:
    """
    150ms 윈도우로 묶은 그룹 내 인접 음 간격이 가장 크게 자주 벌어지는
    피치를 손 분리 기준으로 반환. 유효 데이터 부족 시 C4(60) fallback.
    """
    from collections import defaultdict

    all_notes = [n for inst in midi.instruments for n in inst.notes]
    if len(all_notes) < 20:
        return 60

    all_notes_sorted = sorted(all_notes, key=lambda n: n.start)
    groups: list[list[int]] = []
    current: list[int] = [all_notes_sorted[0].pitch]
    group_start = all_notes_sorted[0].start

    for n in all_notes_sorted[1:]:
        if n.start - group_start <= 0.15:
            current.append(n.pitch)
        else:
            if len(current) >= 2:
                groups.append(sorted(current))
            current = [n.pitch]
            group_start = n.start
    if len(current) >= 2:
        groups.append(sorted(current))

    if not groups:
        return 60

    gap_score: dict[int, float] = defaultdict(float)
    for group in groups:
        for i in range(len(group) - 1):
            gap = group[i + 1] - group[i]
            mid = (group[i] + group[i + 1]) // 2
            if 36 <= mid <= 72:  # C3~C5 범위 내에서만 탐색
                gap_score[mid] += gap

    if not gap_score:
        return 60

    best = max(gap_score, key=lambda p: gap_score[p])
    # 결과가 너무 높으면(C5 이상) 신뢰하지 않고 C4로 fallback
    return best if best <= 65 else 60

def _normalize_bpm(bpm: float) -> float:
    """BPM을 60–200 음악적 유효 범위로 정규화."""
    while bpm < 60:
        bpm *= 2
    while bpm > 200:
        bpm /= 2
    return float(bpm)


def _get_device() -> str:
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


# ---------------------------------------------------------------------------
# 내부 헬퍼: pyin 선율 추출
# ---------------------------------------------------------------------------

def _pyin_melody(
    y: np.ndarray,
    sr: int,
    beat_times: np.ndarray,
    bpm: float,
    hop: int = 512,
) -> "list[pretty_midi.Note]":
    """
    librosa.pyin 으로 단음 선율을 추출하고 beat grid 에 양자화한 Note 리스트 반환.

    pyin (McLeod & Wyvill, 2005 / librosa 구현)
    - 기본 피치 추적 알고리즘 YIN 의 확률론적 확장
    - voiced/unvoiced 구분이 명확해 piano 선율에 적합
    - 최고 강도의 단일 피치를 반환 → 폴리포닉 공명 자동 무시
    """
    import librosa
    import pretty_midi

    f0, voiced, _ = librosa.pyin(
        y,
        sr=sr,
        fmin=librosa.note_to_hz("C2"),   # 최저 C2 (피아노 최저음 A0 에서 여유)
        fmax=librosa.note_to_hz("C8"),   # 최고 C8
        hop_length=hop,
    )
    times = librosa.times_like(f0, sr=sr, hop_length=hop)

    # 연속 voiced 구간을 하나의 음표로 묶기
    notes: list[pretty_midi.Note] = []
    in_note   = False
    note_start = 0.0
    note_pitch = 0

    for t, freq, v in zip(times, f0, voiced):
        if v and freq is not None and not np.isnan(freq) and freq > 0:
            midi_p = int(round(librosa.hz_to_midi(freq)))
            midi_p = max(21, min(108, midi_p))   # 피아노 음역 클램프

            if not in_note:
                in_note    = True
                note_start = float(t)
                note_pitch = midi_p
            elif midi_p != note_pitch:
                # 피치 변화 → 이전 음표 종료 후 새 음표 시작
                notes.append(pretty_midi.Note(
                    velocity=80, pitch=note_pitch,
                    start=note_start, end=float(t),
                ))
                note_start = float(t)
                note_pitch = midi_p
        else:
            if in_note:
                notes.append(pretty_midi.Note(
                    velocity=80, pitch=note_pitch,
                    start=note_start, end=float(t),
                ))
                in_note = False

    if in_note:
        notes.append(pretty_midi.Note(
            velocity=80, pitch=note_pitch,
            start=note_start, end=float(times[-1]),
        ))

    # beat grid 에 양자화
    return _quantize_notes_to_grid(notes, beat_times, bpm)


def _quantize_notes_to_grid(
    notes: "list[pretty_midi.Note]",
    beat_times: np.ndarray,
    bpm: float,
) -> "list[pretty_midi.Note]":
    """onset·duration 을 beat-subdivision grid 로 스냅."""
    import pretty_midi

    if len(beat_times) < 2:
        subdiv = 60.0 / bpm / _N_DIV
        result = []
        for n in notes:
            s = round(n.start / subdiv) * subdiv
            dur_raw = max(n.end - n.start, subdiv)
            k   = max(1, round(dur_raw / subdiv))
            STD = [1, 2, 4, 8, 16]   # 점음표(3,6,12) 제외 — 비-그리드 위치 방지
            k   = min(STD, key=lambda x: abs(x - k))
            e   = s + k * subdiv
            if e > s:
                result.append(pretty_midi.Note(velocity=n.velocity, pitch=n.pitch, start=s, end=e))
        return result

    # beat 위치 기반 grid
    grid: list[float] = []
    for i in range(len(beat_times) - 1):
        t0, t1 = float(beat_times[i]), float(beat_times[i + 1])
        for k in range(_N_DIV):
            grid.append(t0 + (t1 - t0) * k / _N_DIV)
    grid.append(float(beat_times[-1]))
    avg_beat = float(np.mean(np.diff(beat_times)))
    for k in range(1, 4 * 4 * _N_DIV + 1):
        grid.append(float(beat_times[-1]) + avg_beat / _N_DIV * k)
    grid_arr = np.array(sorted(set(grid)))

    STD = np.array([1, 2, 4, 8, 16])   # 점음표(3,6,12) 제외
    result = []
    for n in notes:
        si   = int(np.argmin(np.abs(grid_arr - n.start)))
        s    = float(grid_arr[si])
        ei   = int(np.argmin(np.abs(grid_arr - n.end)))
        k    = max(1, ei - si)
        k    = int(STD[np.argmin(np.abs(STD - k))])
        ei2  = min(si + k, len(grid_arr) - 1)
        e    = float(grid_arr[ei2])
        if e > s:
            result.append(pretty_midi.Note(velocity=n.velocity, pitch=n.pitch, start=s, end=e))
    return result


# ---------------------------------------------------------------------------
# 내부 헬퍼: 음표 성부 분류 (선율 중심 재설계)
# ---------------------------------------------------------------------------

def _classify_voices(
    cleaned_midi: "pretty_midi.PrettyMIDI",
    pyin_notes: "list[pretty_midi.Note]",
    split_pitch: int,
    bpm: float,
) -> "tuple[list, list]":
    """
    [piano_transcription 주 소스 + pyin 선율 힌트]

    오른손 구성:
      1. split_pitch 이상 piano_trans 음표 → onset당 _MAX_RH_CHORD 음.
         pyin이 같은 onset에 있으면 pyin 피치에 가장 가까운 음을 최상위로 정렬
         (선율 음표가 상성부에 오도록).
      2. pyin이 검출했지만 piano_trans에 없는 onset → pyin 음표 직접 추가
         (piano_trans가 놓친 약한 선율음 보완).

    왼손 구성:
      - split_pitch 미만 piano_trans 음표
      - velocity ≥ 40 (공명·페달 잔향 음표만 제거, 정상 약타 유지)
      - onset당 최대 _MAX_LH_CHORD 음
    """
    import pretty_midi

    # ── piano_transcription 음표를 split으로 분리 ───────────────────
    rh_by_onset: dict[float, list] = defaultdict(list)
    lh_raw:      list              = []

    for inst in cleaned_midi.instruments:
        for note in sorted(inst.notes, key=lambda n: n.start):
            if note.pitch < split_pitch:
                lh_raw.append(note)
            else:
                rh_by_onset[round(note.start, 3)].append(note)

    # pyin onset 색인 (onset→Note)
    pyin_by_onset: dict[float, "pretty_midi.Note"] = {}
    for pn in sorted(pyin_notes, key=lambda n: n.start):
        pyin_by_onset[round(pn.start, 3)] = pn

    # ── 오른손: piano_trans 주 소스, pyin으로 상성부 우선 정렬 ────────
    rh_notes:       list = []
    covered_onsets: set  = set()

    for onset in sorted(rh_by_onset):
        group = list(rh_by_onset[onset])

        if onset in pyin_by_onset:
            pyin_p = pyin_by_onset[onset].pitch
            # pyin 피치와 가까운 음을 우선, 동률이면 높은 음 먼저
            group.sort(key=lambda n: (abs(n.pitch - pyin_p), -n.pitch))
        else:
            # pyin 힌트 없으면 가장 높은 음(주 선율)이 앞에 오도록
            group.sort(key=lambda n: -n.pitch)

        rh_notes.extend(group[:_MAX_RH_CHORD])
        covered_onsets.add(onset)

    # piano_trans에 없는 pyin onset 보완 (놓친 선율음 복구)
    for onset, pn in pyin_by_onset.items():
        if onset not in covered_onsets and pn.pitch >= split_pitch:
            rh_notes.append(pn)

    # ── 왼손: velocity ≥ 40, onset당 최대 _MAX_LH_CHORD 음 ──────────
    lh_by_onset: dict[float, list] = defaultdict(list)
    for note in lh_raw:
        if note.velocity >= 40:
            lh_by_onset[round(note.start, 3)].append(note)

    lh_notes: list = []
    for onset in sorted(lh_by_onset):
        group = sorted(lh_by_onset[onset], key=lambda n: n.velocity, reverse=True)
        lh_notes.extend(group[:_MAX_LH_CHORD])

    rh_notes = sorted(rh_notes, key=lambda n: n.start)
    lh_notes = sorted(lh_notes, key=lambda n: n.start)
    return rh_notes, lh_notes


# ---------------------------------------------------------------------------
# 내부 헬퍼: Beat-aligned 퀀타이즈
# ---------------------------------------------------------------------------

def _classify_beat_grid(onsets: list[float], t0: float, t1: float) -> str:
    """
    Beat 구간 [t0, t1) 내 onset 분포로 binary(4분할) / triplet(3분할) 판정.

    연속 onset 간격이 beat/4(16분음표) 와 beat/3(셋잇단 8분) 중
    어느 쪽에 더 가까운지를 다수결로 결정한다.
    tolerance 기반 방식은 두 그리드 간격(beat의 1/12≈8.3%)이 좁아 오탐이 많으므로
    "어느 쪽에 더 가깝냐" 비교를 사용한다.

    조건: 연속 구간 중 2개 이상이 triplet 쪽 더 가깝고 binary보다 많을 때 반환.
    """
    if len(onsets) < 3:
        return "binary"
    dur = t1 - t0
    triplet_iv = dur / 3   # 셋잇단 8분 간격
    binary_iv  = dur / 4   # 16분음표 간격

    sorted_o = sorted(onsets)
    intervals = [sorted_o[i + 1] - sorted_o[i] for i in range(len(sorted_o) - 1)]

    t_score = sum(1 for iv in intervals if abs(iv - triplet_iv) < abs(iv - binary_iv))
    b_score = sum(1 for iv in intervals if abs(iv - binary_iv) <= abs(iv - triplet_iv))

    return "triplet" if t_score >= 2 and t_score > b_score else "binary"


def _beat_quantize(
    midi: "pretty_midi.PrettyMIDI",
    bpm: float,
    beat_times: np.ndarray,
    n_div: int = _N_DIV,
) -> "pretty_midi.PrettyMIDI":
    """
    librosa beat_track 기반 musical-grid 퀀타이즈.

    beat 마다 binary(4분할) / triplet(3분할) 그리드를 독립적으로 결정해
    셋잇단음 패턴을 binary 그리드로 왜곡하지 않는다.
    MIDI resolution=480 (3의 배수) 으로 저장해 triplet 음가를 정수 tick 으로 표현.
    """
    import pretty_midi

    avg_beat = float(np.mean(np.diff(beat_times))) if len(beat_times) > 1 else 60.0 / bpm
    avg_sub  = avg_beat / n_div

    if len(beat_times) < 2:
        return _uniform_quantize(midi, bpm, avg_sub)

    # ── per-beat 그리드 구축 ───────────────────────────────────────────
    all_onsets = sorted({round(n.start, 4) for inst in midi.instruments for n in inst.notes})

    # 초기 버전: triplet 감지 비활성화 — 항상 binary(4분할) 그리드 사용.
    # per-beat triplet 감지를 켜면 같은 마디에 binary·triplet이 섞여
    # music21이 12-tuplet을 생성한다. 설계 문서: "초기 버전 triplet 미지원".
    modes: list[str]        = []
    grids: list[np.ndarray] = []
    for i in range(len(beat_times) - 1):
        t0, t1 = float(beat_times[i]), float(beat_times[i + 1])
        dur    = t1 - t0
        div    = n_div   # 항상 binary(4분할) — triplet 감지 제거
        grids.append(np.array([t0 + dur * k / div for k in range(div + 1)]))
        modes.append("binary")

    # 악곡 끝 연장 binary grid
    ext = np.array([float(beat_times[-1]) + avg_sub * k for k in range(1, 4 * 4 * n_div + 1)])

    def snap_onset(t: float) -> tuple[float, str, int]:
        for i in range(len(beat_times) - 1):
            if float(beat_times[i]) <= t < float(beat_times[i + 1]):
                idx = int(np.argmin(np.abs(grids[i] - t)))
                return float(grids[i][idx]), modes[i], i
        idx = int(np.argmin(np.abs(ext - t)))
        return float(ext[idx]), "binary", -1

    # 이진 그리드만 사용 — 1=16분, 2=8분, 4=4분, 8=2분, 16=온음표
    # 점음표(3=점8분, 6=점4분, 12=점2분) 제외: 비-그리드 offset 방지
    _S_BIN = np.array([1, 2, 4, 8, 16])

    def snap_dur(s: float, e: float, mode: str, bidx: int) -> float:
        # triplet 감지 제거: mode는 항상 "binary", 이진 그리드만 사용
        k = int(_S_BIN[np.argmin(np.abs(_S_BIN - max(1, round((e - s) / avg_sub))))])
        return k * avg_sub

    result = pretty_midi.PrettyMIDI(initial_tempo=bpm, resolution=480)
    for inst in midi.instruments:
        notes = []
        for note in sorted(inst.notes, key=lambda n: n.start):
            s, mode, bidx = snap_onset(note.start)
            d = snap_dur(s, note.end, mode, bidx)
            if d > 0:
                notes.append(pretty_midi.Note(
                    velocity=note.velocity, pitch=note.pitch,
                    start=s, end=s + d,
                ))
        new_inst = pretty_midi.Instrument(
            program=inst.program, is_drum=inst.is_drum, name=inst.name,
        )
        new_inst.notes = sorted(notes, key=lambda n: n.start)
        result.instruments.append(new_inst)
    return result


def _uniform_quantize(
    midi: "pretty_midi.PrettyMIDI",
    bpm: float,
    subdiv_dur: float,
) -> "pretty_midi.PrettyMIDI":
    """uniform BPM grid 퀀타이즈 (beat_times 부족 시 fallback)."""
    import pretty_midi

    STD = [1, 2, 4, 8, 16]    # 점음표(3,6,12) 제외
    result = pretty_midi.PrettyMIDI(initial_tempo=bpm, resolution=480)
    for inst in midi.instruments:
        notes = []
        for note in sorted(inst.notes, key=lambda n: n.start):
            s = round(note.start / subdiv_dur) * subdiv_dur
            n_s = max(1, round((note.end - note.start) / subdiv_dur))
            nearest = min(STD, key=lambda x: abs(x - n_s))
            e = s + nearest * subdiv_dur
            if e > s:
                notes.append(pretty_midi.Note(
                    velocity=note.velocity, pitch=note.pitch, start=s, end=e,
                ))
        new_inst = pretty_midi.Instrument(
            program=inst.program, is_drum=inst.is_drum, name=inst.name,
        )
        new_inst.notes = sorted(notes, key=lambda n: n.start)
        result.instruments.append(new_inst)
    return result


# ---------------------------------------------------------------------------
# 내부 헬퍼: MusicXML 생성
# ---------------------------------------------------------------------------

def _compute_split_pitch(score: stream.Score) -> int:
    """가온 도(C4, MIDI 60) 고정 기준."""
    return 60


def _split_hands(score: stream.Score, bpm: float = 120.0) -> stream.Score:
    """
    MIDI → 오른손/왼손 파트 분리.

    _transcribe 가 이미 두 Instrument 로 RH/LH 를 구분해 저장한 경우
    (name='RH', name='LH') 그대로 사용. 단일 Instrument 인 경우 피치 기반 분리.
    """
    # _transcribe 출력: instrument 이름으로 RH/LH 구분 가능 여부 확인
    # music21이 MIDI 트랙명을 partName으로 보존하지 않을 수 있어, 이름·인덱스 둘 다 시도.
    parts = score.parts
    rh_inst = None
    lh_inst = None

    for p in parts:
        name = (getattr(p, 'partName', '') or '').strip()
        if name in ('RH', 'Piano Right'):
            rh_inst = p
        elif name in ('LH', 'Piano Left'):
            lh_inst = p

    # 이름 매칭 실패 → 파트 수 관계없이 가온 도(C4) 기준 피치 분리
    if rh_inst is None or lh_inst is None:
        rh_inst = lh_inst = None

    # 음표 수집 (_smart_q: 이진 16분음표 그리드로 스냅 — triplet 미지원)
    def collect(parts) -> list[tuple[float, int, float]]:
        out: list[tuple[float, int, float]] = []
        for part in parts:
            for el in part.flatten().notesAndRests:
                if isinstance(el, m21_note.Rest):
                    continue
                offset = _smart_q(float(el.offset))
                ql     = _snap_ql(max(_smart_q(float(el.quarterLength)), _QL_GRID))
                if isinstance(el, m21_note.Note):
                    out.append((offset, el.pitch.midi, ql))
                elif isinstance(el, m21_chord.Chord):
                    for cn in el.notes:
                        out.append((offset, cn.pitch.midi, ql))
        return out

    if rh_inst and lh_inst:
        right_notes = collect([rh_inst])
        left_notes  = collect([lh_inst])
    else:
        split_pitch = _compute_split_pitch(score)
        all_notes   = collect(score.parts)
        right_notes = [(o, p, q) for o, p, q in all_notes if p >= split_pitch]
        left_notes  = [(o, p, q) for o, p, q in all_notes if p < split_pitch]

    # 필요 마디 수
    all_notes = right_notes + left_notes
    if all_notes:
        max_end    = max(o + q for o, _, q in all_notes)
        n_measures = max(4, int(np.ceil(max_end / _MEASURE_QL)))
    else:
        n_measures = 4

    max_per_hand = (_MAX_RH_CHORD, _MAX_LH_CHORD)

    # ── 조성 자동 감지 ─────────────────────────────────────────────────
    detected_key = _detect_key(right_notes + left_notes)

    def build_part(notes: list[tuple[float, int, float]], treble: bool) -> stream.Part:
        by_offset: dict[float, list[tuple[int, float]]] = defaultdict(list)
        for off, pitch, ql in notes:
            by_offset[off].append((pitch, ql))

        part = stream.Part()
        part.insert(0, instrument.Piano())
        part.insert(0, clef.TrebleClef() if treble else clef.BassClef())
        if treble:
            part.insert(0, m21_tempo.MetronomeMark(number=round(bpm)))

        max_chord = max_per_hand[0] if treble else max_per_hand[1]

        for m_idx in range(n_measures):
            m_start = float(m_idx * _MEASURE_QL)
            m_end   = m_start + _MEASURE_QL

            measure = stream.Measure(number=m_idx + 1)

            # 조성·박자표는 첫 마디에만 삽입.
            # 매 마디에 넣으면 악보에 반복 출력돼 시각적으로 지저분해진다.
            if m_idx == 0:
                measure.insert(0, m21_key.KeySignature(detected_key.sharps))
                measure.insert(0, m21_meter.TimeSignature("4/4"))

            # 이 마디 안의 모든 onset을 정렬하여 "다음 onset" 정보 확보
            offsets_in_measure = sorted(o for o in by_offset if m_start <= o < m_end)

            for i, abs_off in enumerate(offsets_in_measure):
                rel_off = abs_off - m_start
                entries = by_offset[abs_off]

                # 마디 끝까지 16분음표 1개 이상의 공간이 없으면 건너뜀.
                remaining = m_end - abs_off
                if remaining < _QL_GRID:
                    continue

                # 다음 onset까지의 거리 — 음표가 다음 음과 겹치지 않도록 상한 설정
                if i + 1 < len(offsets_in_measure):
                    gap_to_next = offsets_in_measure[i + 1] - abs_off
                else:
                    gap_to_next = remaining   # 마디 마지막 음표 → 마디 끝까지 허용

                seen: set[int] = set()
                deduped: list[tuple[int, float]] = []
                for pitch, ql in sorted(entries, key=lambda x: x[0], reverse=treble):
                    if pitch not in seen:
                        seen.add(pitch)
                        deduped.append((pitch, ql))
                deduped = deduped[:max_chord]

                if not deduped:
                    continue

                best_ql = Counter(ql for _, ql in deduped).most_common(1)[0][0]
                # 음표 길이 상한: 마디 끝 AND 다음 onset AND (왼손은 8분음표 최대)
                max_ql = min(remaining, gap_to_next)
                if not treble:
                    # 왼손: 2분음표(2.0 QL) 이하 — 페달 베이스 허용, 지나치게 긴 홀딩 방지
                    max_ql = min(max_ql, 2.0)
                best_ql = _snap_ql(min(best_ql, max_ql))
                if best_ql <= 0:
                    best_ql = _QL_GRID
                # 이진 그리드 전용 — Fraction/tuplet 변환 없음
                exact_ql = best_ql

                pitches = [p for p, _ in deduped]
                if len(pitches) == 1:
                    measure.insert(rel_off, _make_note(pitches[0], exact_ql))
                else:
                    measure.insert(rel_off, m21_chord.Chord(
                        [_make_note(p, exact_ql) for p in pitches],
                        quarterLength=exact_ql,
                    ))

            measure.makeRests(fillGaps=True, inPlace=True)
            part.append(measure)

        # ── Beaming: 박자에 맞게 빔 그룹 정리 ──────────────────────────
        try:
            part.makeBeams(inPlace=True)
        except Exception:
            pass

        # ── Accidentals: 조성 기호 기반 임시표 자동 처리 ────────────────
        # - 조성에 포함된 #/♭은 표기 제거 (중복 임시표 방지)
        # - 조성 외 음에만 임시표 추가
        try:
            part.makeAccidentals(
                useKeySignature=True,
                searchKeySignatureByContext=True,
                cautionaryPitchClass=True,
                cautionaryAll=False,
                inPlace=True,
            )
        except Exception:
            pass

        return part

    right  = build_part(right_notes, treble=True)
    left   = build_part(left_notes,  treble=False)

    # 높음음자리표(오른손)를 첫 번째 파트로, 낮은음자리표(왼손)를 두 번째 파트로.
    # insert(0, ...) 두 번 호출 시 삽입 순서가 렌더러에 따라 뒤집힐 수 있어
    # append 로 명시적 순서 보장.
    result = stream.Score()
    result.append(right)
    result.append(left)
    return result


# ---------------------------------------------------------------------------
# 내부 헬퍼: 오디오 전처리
# ---------------------------------------------------------------------------

def _separate_piano(audio_path: str, output_dir: str, progress_cb=None) -> str:
    """htdemucs_6s 모델로 피아노 스템만 추출."""
    import re as _re

    out_path = Path(output_dir) / "demucs"
    out_path.mkdir(parents=True, exist_ok=True)

    cmd = [sys.executable, "-m", "demucs", "-n", _DEMUCS_MODEL,
           "-o", str(out_path), audio_path]

    if progress_cb:
        # stderr를 파이프로 받아 tqdm 진행률(X%) 실시간 파싱 → 전체 3~29% 구간 매핑
        # 백그라운드 스레드에서 실행되므로 블로킹 read1이 이벤트 루프를 막지 않음
        proc = subprocess.Popen(cmd, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL)
        buf = b""
        while True:
            chunk = proc.stderr.read1(512)
            if not chunk:
                break
            buf += chunk
            parts = _re.split(b"[\r\n]", buf)
            buf = parts[-1]
            for part in parts[:-1]:
                text = part.decode("utf-8", errors="replace")
                m = _re.search(r"(\d+)%", text)
                if m:
                    demucs_pct = int(m.group(1))
                    progress_cb(3 + min(26, int(demucs_pct * 0.26)))
        proc.wait()
        if proc.returncode != 0:
            raise subprocess.CalledProcessError(proc.returncode, "demucs")
    else:
        subprocess.run(cmd, check=True)

    piano_wav = out_path / _DEMUCS_MODEL / Path(audio_path).stem / f"{_PIANO_STEM}.wav"
    if not piano_wav.exists():
        raise FileNotFoundError(f"피아노 스템 파일을 찾을 수 없습니다: {piano_wav}")
    return str(piano_wav)


def _detect_bpm(wav_path: str) -> float:
    import librosa
    y, sr = librosa.load(wav_path, sr=None, mono=True)
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    bpm = float(tempo[0]) if hasattr(tempo, '__len__') else float(tempo)
    while bpm > 200:
        bpm /= 2
    return bpm


def _transcribe(wav_path: str, output_dir: str, progress_cb=None) -> str:
    """
    오디오 → 정제된 2트랙 MIDI (RH / LH 피치 분리).

    TRANSCRIPTION_MODEL 설정으로 채보 모델 전환:
      "piano_transcription"  — Bytedance ICASSP 2021 (기본, 폴리포닉 정확도 높음)
      "basic_pitch"          — Spotify ICASSP 2022  (설치 후 대체 가능)

    전략: 폴리포닉 채보 → beat-aligned 퀀타이즈 → 경량 후처리 → 피치 기반 손 분리.
    pyin 선율 분리는 MIDI 단계에서 제외 (musicxml 변환 시 _split_hands 에서 처리).
    """
    from core.config import settings
    import librosa
    import pretty_midi

    # ── 1. 오디오 로드 ─────────────────────────────────────────────────
    y, sr = librosa.load(wav_path, sr=None, mono=True)

    # ── 2. BPM + beat 위치 ────────────────────────────────────────────
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    tempo_arr = librosa.feature.tempo(onset_envelope=onset_env, aggregate=None)
    bpm       = _normalize_bpm(float(np.median(tempo_arr)))
    _, beat_frames = librosa.beat.beat_track(y=y, sr=sr, bpm=bpm)
    beat_times = librosa.frames_to_time(beat_frames, sr=sr)

    # ── 3. 폴리포닉 채보 ──────────────────────────────────────────────
    model_name = settings.TRANSCRIPTION_MODEL.lower().strip()

    raw_mid_path = Path(output_dir) / "original_raw.mid"

    if model_name == "basic_pitch":
        from instruments.piano.basicpitch_adapter import transcribe_basic_pitch
        raw_midi = transcribe_basic_pitch(wav_path)
        # basic_pitch는 PrettyMIDI 객체만 반환하므로 디스크에 저장
        raw_midi.write(str(raw_mid_path))

    elif model_name == "piano_transcription":
        try:
            from piano_transcription_inference import (
                PianoTranscription, sample_rate as PT_SR,
            )
        except ImportError as exc:
            raise ImportError("pip install piano_transcription_inference") from exc

        audio_pt    = librosa.load(wav_path, sr=PT_SR, mono=True)[0].astype("float32")
        transcriber = PianoTranscription(device=_get_device())

        if progress_cb:
            import builtins as _builtins, re as _re
            _orig_print = _builtins.print

            def _tracking_print(*args, **kwargs):
                _orig_print(*args, **kwargs)
                text = " ".join(str(a) for a in args)
                m = _re.search(r"Segment\s+(\d+)\s*/\s*(\d+)", text)
                if m:
                    seg, total = int(m.group(1)), int(m.group(2))
                    progress_cb(30 + min(29, int((seg + 1) / max(total, 1) * 30)))

            _builtins.print = _tracking_print
            try:
                transcriber.transcribe(audio_pt, str(raw_mid_path))
            finally:
                _builtins.print = _orig_print
        else:
            transcriber.transcribe(audio_pt, str(raw_mid_path))

        raw_midi = pretty_midi.PrettyMIDI(str(raw_mid_path))

    else:
        raise ValueError(
            f"알 수 없는 TRANSCRIPTION_MODEL={model_name!r}. "
            "유효값: 'piano_transcription', 'basic_pitch'"
        )

    # ── 4. Beat-aligned 퀀타이즈 ──────────────────────────────────────
    quantized = _beat_quantize(raw_midi, bpm, beat_times, n_div=_N_DIV)

    # ── 5. 경량 후처리 — ghost note 제거 + 화음 보존 ──────────────────
    cleaned = clean_midi(quantized, PRESETS["midi_clean"])

    # ── 6. 적응형 split_pitch 계산 (동시음 간격 기반) ─────────────────
    split_pitch = _calc_split_pitch(cleaned)

    # ── 7. 피치 기반 손 분리 + 2트랙 저장 ────────────────────────────
    rh_notes: list = []
    lh_notes: list = []
    for inst in cleaned.instruments:
        for note in inst.notes:
            (rh_notes if note.pitch >= split_pitch else lh_notes).append(note)

    result  = pretty_midi.PrettyMIDI(initial_tempo=bpm)
    rh_inst = pretty_midi.Instrument(program=0, name="RH")
    lh_inst = pretty_midi.Instrument(program=0, name="LH")
    rh_inst.notes = sorted(rh_notes, key=lambda n: n.start)
    lh_inst.notes = sorted(lh_notes, key=lambda n: n.start)
    result.instruments = [rh_inst, lh_inst]

    out = Path(output_dir) / "original.mid"
    result.write(str(out))
    
    # librosa가 감지한 BPM을 sidecar 파일로 저장
    import json
    (Path(output_dir) / "detected_bpm.json").write_text(json.dumps({"bpm": round(bpm, 4)}))

    return str(out)
