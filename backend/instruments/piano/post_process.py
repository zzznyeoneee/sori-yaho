"""
담당: 김진현
Basic Pitch raw MIDI 후처리 — 노이즈/배음/중복 음표 제거 + 퀀타이즈

converter.py 내부에서 호출됨. 외부에서 직접 쓸 경우:
    from midi_processing.post_process import clean_midi, CleanConfig, PRESETS
"""
from dataclasses import dataclass

import numpy as np
import pretty_midi


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

@dataclass
class CleanConfig:
    # 1. 짧은 음표 제거
    min_note_duration: float = 0.1          # 초 (약 16분음표 기준)

    # 2. 배음(오버톤) 유령 음표 필터
    overtone_window: float = 0.05           # 동시 발음 판단 윈도우 (초)
    overtone_velocity_ratio: float = 0.4    # 주음 대비 40% 미만이면 배음 의심

    # 3. 음표 밀도 제한
    max_notes_per_window: int = 6
    density_window: float = 0.1

    # 4. 퀀타이즈 (4/4 전용: 완전 스냅으로 music21이 clean한 음가를 읽도록)
    quantize_strength: float = 1.0          # 0=없음, 1=완전 스냅
    min_grid: float = 0.25                  # 그리드 단위 (박자의 1/4 = 16분음표)

    # 5. 중복 음표
    duplicate_window: float = 0.05

    # 6. velocity
    min_velocity: int = 20
    velocity_smooth: bool = True
    velocity_smooth_window: int = 5

    # 7. 통계적 이상치 제거 (0=비활성)
    outlier_velocity_sigma: float = 0.0     # velocity z-score 하한 (ghost note 제거)
    max_note_duration_beats: float = 0.0    # 최대 음표 길이(박자 단위, 0=비활성)
    use_isolated_filter: bool = True        # filter_isolated_notes 활성화 여부


# 장르별 프리셋
PRESETS: dict[str, CleanConfig] = {
    "ballad": CleanConfig(
        min_note_duration=0.12,
        overtone_velocity_ratio=0.45,
        quantize_strength=0.85,
        min_grid=0.25,
    ),
    "classical": CleanConfig(
        min_note_duration=0.08,
        overtone_velocity_ratio=0.35,
        quantize_strength=0.6,
        min_grid=0.125,
    ),
    "pop": CleanConfig(
        min_note_duration=0.1,
        overtone_velocity_ratio=0.4,
        quantize_strength=0.9,
        min_grid=0.25,
    ),
    # piano_transcription_inference / basic_pitch + beat-aligned 퀀타이즈 전용.
    # beat_quantize 가 이미 onset/duration 을 musical grid 에 정렬했으므로
    # quantize_strength=0.0 으로 재덮어쓰기를 방지한다.
    # ── 강화 버전 (잡음 최소화, 선율 중심 출력) ──────────────────────
    # onset_threshold=0.6 + 이 프리셋 조합으로 ghost note를 대폭 줄인다.
    "classical_4_4": CleanConfig(
        # 0.12s ≈ 120bpm 16분음표(0.125s)와 거의 동일
        # → 16분음표보다 짧은 잡음은 모두 제거
        min_note_duration=0.12,
        overtone_window=0.04,
        overtone_velocity_ratio=0.60,     # 주음 대비 60% 미만 배음 → 유령음 판정 (↑ 강화)
        max_notes_per_window=3,           # 한 순간 최대 3음 — 4음짜리 화음 덩어리 제거
        density_window=0.08,              # 80ms 윈도우 (더 촘촘한 검사)
        quantize_strength=0.0,            # beat_quantize 완료 → 재퀀타이즈 금지
        min_grid=0.25,
        duplicate_window=0.04,            # 40ms 이내 중복 제거 (↑ 강화)
        min_velocity=35,                  # 35 미만 → 공명·페달 잔향 제거 (↑ 강화)
        velocity_smooth=True,
        velocity_smooth_window=9,         # 더 넓은 스무딩으로 velocity 안정화
        outlier_velocity_sigma=1.8,       # 하위 ~3.6% 극단 저velocity 제거 (↑ 강화)
        max_note_duration_beats=4.0,
        use_isolated_filter=True,
    ),
    # MIDI 전용 경량 후처리 — piano_transcription 결과의 폴리포니 최대 보존.
    # ghost note(짧고 약한 음)만 제거하고 화음·약타는 남긴다.
    "midi_clean": CleanConfig(
        min_note_duration=0.08,        # 80ms 미만만 제거 (16분음표≈125ms 기준 여유)
        overtone_window=0.05,
        overtone_velocity_ratio=0.30,  # 30% 미만만 배음 판정 — 정상 화음은 유지
        max_notes_per_window=8,        # 한 순간 최대 8음 — 두꺼운 화음 보존
        density_window=0.08,
        quantize_strength=0.0,         # beat_quantize 완료 → 재덮어쓰기 금지
        min_grid=0.25,
        duplicate_window=0.04,
        min_velocity=20,               # 20 미만만 제거 (부드러운 화음·약타 유지)
        velocity_smooth=True,
        velocity_smooth_window=5,
        outlier_velocity_sigma=0.0,    # 통계 기반 제거 비활성
        max_note_duration_beats=8.0,   # 2온음표까지 허용 (페달 지속음 보존)
        use_isolated_filter=False,     # 고립음 필터 비활성 (단독 음표도 유지)
    ),
}


# ---------------------------------------------------------------------------
# 메인 진입점
# ---------------------------------------------------------------------------

def clean_midi(midi: pretty_midi.PrettyMIDI, cfg: CleanConfig = None, bpm: float = None) -> pretty_midi.PrettyMIDI:
    """
    Basic Pitch raw MIDI 후처리 파이프라인.
    순서: 짧은음표 → velocity → 중복 → 배음 → 밀도 →
          [velocity이상치] → [고립음표] → 퀀타이즈 → 음가스냅 →
          [음길이캡] → 겹침병합 → 스무딩
    """
    cfg = cfg or CleanConfig()
    bpm = bpm if bpm else _estimate_clean_tempo(midi)
    result = pretty_midi.PrettyMIDI(initial_tempo=bpm)

    for inst in midi.instruments:
        notes = inst.notes[:]

        notes = filter_short_notes(notes, cfg.min_note_duration)
        notes = filter_low_velocity(notes, cfg.min_velocity)
        notes = filter_duplicate_notes(notes, cfg.duplicate_window)
        notes = filter_overtone_ghosts(notes, cfg.overtone_window, cfg.overtone_velocity_ratio)
        notes = filter_density_spike(notes, cfg.max_notes_per_window, cfg.density_window)

        # 통계적 이상치 제거 (classical_4_4 프리셋에서 활성화)
        if cfg.outlier_velocity_sigma > 0:
            notes = filter_outlier_velocities(notes, cfg.outlier_velocity_sigma)
            if cfg.use_isolated_filter:
                notes = filter_isolated_notes(notes)

        notes = quantize_notes(notes, bpm, cfg.quantize_strength, cfg.min_grid)
        notes = snap_note_durations(notes, bpm)

        if cfg.max_note_duration_beats > 0:
            notes = cap_note_durations(notes, bpm, cfg.max_note_duration_beats)

        notes = merge_overlapping_notes(notes)

        if cfg.velocity_smooth:
            notes = smooth_velocity(notes, cfg.velocity_smooth_window)

        new_inst = pretty_midi.Instrument(
            program=inst.program,
            is_drum=inst.is_drum,
            name=inst.name,
        )
        new_inst.notes = sorted(notes, key=lambda n: n.start)
        result.instruments.append(new_inst)

    return result


# ---------------------------------------------------------------------------
# 필터 구현
# ---------------------------------------------------------------------------

def filter_short_notes(notes: list, min_dur: float) -> list:
    """
    min_dur 미만 음표 제거.
    직전 음표와 피치가 같으면 삭제 대신 연장 처리 (멜로디 단절 방지).
    """
    notes = sorted(notes, key=lambda n: n.start)
    result = []

    for note in notes:
        dur = note.end - note.start
        if dur >= min_dur:
            result.append(note)
        elif result and result[-1].pitch == note.pitch:
            prev = result[-1]
            result[-1] = pretty_midi.Note(
                velocity=prev.velocity,
                pitch=prev.pitch,
                start=prev.start,
                end=max(prev.end, note.end),
            )

    return result


def filter_low_velocity(notes: list, min_vel: int) -> list:
    """velocity min_vel 미만 음표 제거"""
    return [n for n in notes if n.velocity >= min_vel]


def filter_duplicate_notes(notes: list, window: float) -> list:
    """
    같은 시간 윈도우 내 동일 피치 중복 음표 제거.
    velocity 높은 것만 남김.
    """
    notes = sorted(notes, key=lambda n: (n.start, n.pitch))
    result: list[pretty_midi.Note] = []

    for note in notes:
        is_dup = any(
            abs(prev.start - note.start) <= window and prev.pitch == note.pitch
            for prev in result[-10:]
        )
        if not is_dup:
            result.append(note)

    return result


def filter_overtone_ghosts(notes: list, window: float, velocity_ratio: float) -> list:
    """
    배음 관계 음표 중 velocity가 주음 대비 velocity_ratio 미만이면 유령 음표로 판단해 제거.
    배음 인터벌: 완전5도(7), 옥타브(12), 옥타브+5도(19), 2옥타브(24)
    """
    OVERTONE_INTERVALS = {7, 12, 19, 24}

    notes = sorted(notes, key=lambda n: n.start)
    remove_set: set[int] = set()

    for i, note in enumerate(notes):
        if i in remove_set:
            continue

        simultaneous = [
            (j, n) for j, n in enumerate(notes)
            if j != i
            and j not in remove_set
            and abs(n.start - note.start) <= window
        ]

        for j, other in simultaneous:
            if abs(other.pitch - note.pitch) not in OVERTONE_INTERVALS:
                continue

            if note.velocity >= other.velocity:
                quieter_idx, louder_vel = j, note.velocity
            else:
                quieter_idx, louder_vel = i, other.velocity

            if notes[quieter_idx].velocity < louder_vel * velocity_ratio:
                remove_set.add(quieter_idx)

    return [n for i, n in enumerate(notes) if i not in remove_set]


def filter_density_spike(notes: list, max_count: int, window: float = 0.1) -> list:
    """짧은 윈도우 내 음표가 max_count 초과 시 velocity 낮은 것부터 제거."""
    notes = sorted(notes, key=lambda n: n.start)
    keep = [True] * len(notes)

    for i, note in enumerate(notes):
        if not keep[i]:
            continue

        window_idxs = [
            j for j, n in enumerate(notes)
            if keep[j] and abs(n.start - note.start) <= window
        ]

        if len(window_idxs) > max_count:
            window_idxs_sorted = sorted(
                window_idxs, key=lambda j: notes[j].velocity, reverse=True
            )
            for j in window_idxs_sorted[max_count:]:
                keep[j] = False

    return [n for i, n in enumerate(notes) if keep[i]]


def filter_outlier_velocities(notes: list, sigma: float) -> list:
    """
    velocity 분포에서 z-score 기준 하위 이상치 음표 제거.
    클래식 피아노의 배음/공명으로 발생하는 저velocity 유령 음표를 통계적으로 제거한다.
    sigma=1.5 권장 (하위 약 7% 제거).
    """
    if len(notes) < 10 or sigma <= 0:
        return notes
    vels = np.array([n.velocity for n in notes], dtype=float)
    mean, std = vels.mean(), max(vels.std(), 1.0)
    lo = mean - sigma * std
    return [n for n in notes if n.velocity >= lo]


def filter_isolated_notes(
    notes: list,
    time_window: float = 0.5,
    pitch_window: int = 12,
    velocity_threshold: int = 55,
) -> list:
    """
    주변에 비슷한 피치 음표가 없으면서 velocity가 낮은 고립 음표 제거.
    클래식 피아노에서 단독으로 뜨는 유령 채보를 제거한다.

    time_window:        이 시간(초) 이내 이웃 탐색
    pitch_window:       이 반음 이내를 '비슷한 피치'로 판단
    velocity_threshold: 이 값 이상이면 고립 여부와 무관하게 유지
    """
    if not notes:
        return notes
    notes = sorted(notes, key=lambda n: n.start)
    keep = [True] * len(notes)

    for i, note in enumerate(notes):
        if note.velocity >= velocity_threshold:
            continue  # 충분히 큰 음표는 항상 유지

        # 주변 후보 범위 한정 (정렬 돼 있으므로 ±30개 정도만 확인)
        lo = max(0, i - 30)
        hi = min(len(notes), i + 30)
        has_neighbor = any(
            j != i
            and keep[j]
            and abs(notes[j].start - note.start) <= time_window
            and abs(notes[j].pitch - note.pitch) <= pitch_window
            for j in range(lo, hi)
        )
        if not has_neighbor:
            keep[i] = False

    return [n for i, n in enumerate(notes) if keep[i]]


def cap_note_durations(notes: list, bpm: float, max_beats: float) -> list:
    """
    음표 길이를 max_beats 박자로 제한.
    페달 지속음이나 채보 오류로 생긴 비정상적으로 긴 음표를 자른다.
    """
    if not notes or max_beats <= 0:
        return notes
    max_dur = (60.0 / bpm) * max_beats
    result = []
    for n in notes:
        if n.end - n.start > max_dur:
            result.append(pretty_midi.Note(
                velocity=n.velocity, pitch=n.pitch,
                start=n.start, end=n.start + max_dur,
            ))
        else:
            result.append(n)
    return result


def quantize_notes(notes: list, bpm: float, strength: float, min_grid: float) -> list:
    """strength=1.0: 완전 스냅 / 0.0: 원본 유지."""
    if strength == 0.0:
        return notes

    beat_dur = 60.0 / bpm
    grid_dur = beat_dur * min_grid

    result = []
    for note in notes:
        s = _snap(note.start, grid_dur, strength)
        e = _snap(note.end, grid_dur, strength)
        if e <= s:
            e = s + grid_dur
        result.append(
            pretty_midi.Note(velocity=note.velocity, pitch=note.pitch, start=s, end=e)
        )
    return result


def snap_note_durations(notes: list, bpm: float) -> list:
    """
    각 음표의 길이를 표준 음가(이진 + 셋잇단)로 스냅.
    셋잇단 8분(beat/3), 4분(2*beat/3), 2분(4*beat/3) 포함.
    """
    beat = 60.0 / bpm
    grid = beat * 0.25  # 16분음표 (최소 단위)
    binary  = [grid * k for k in (1, 2, 3, 4, 6, 8, 12, 16)]
    triplet = [beat * k / 3 for k in (1, 2, 4)]   # 셋잇단 8분, 4분, 2분
    std_durs = sorted(set(binary + triplet))

    result = []
    for note in notes:
        dur = note.end - note.start
        nearest = min(std_durs, key=lambda d: abs(d - dur))
        nearest = max(nearest, grid)  # 최소 16분음표 보장
        result.append(
            pretty_midi.Note(
                velocity=note.velocity,
                pitch=note.pitch,
                start=note.start,
                end=note.start + nearest,
            )
        )
    return result


def merge_overlapping_notes(notes: list) -> list:
    """같은 피치에서 끝나기 전 다시 시작하는 음표를 병합 (레가토 / 채보 오류 수정)."""
    notes = sorted(notes, key=lambda n: (n.pitch, n.start))
    result: list[pretty_midi.Note] = []

    for note in notes:
        if (
            result
            and result[-1].pitch == note.pitch
            and result[-1].end >= note.start - 0.05
        ):
            prev = result[-1]
            result[-1] = pretty_midi.Note(
                velocity=max(prev.velocity, note.velocity),
                pitch=prev.pitch,
                start=prev.start,
                end=max(prev.end, note.end),
            )
        else:
            result.append(note)

    return result


def smooth_velocity(notes: list, window_size: int = 5) -> list:
    """이동평균으로 velocity 튀는 값 완화"""
    if len(notes) < window_size:
        return notes

    notes = sorted(notes, key=lambda n: n.start)
    vels = np.array([n.velocity for n in notes], dtype=float)
    kernel = np.ones(window_size) / window_size
    smoothed = np.clip(np.convolve(vels, kernel, mode="same"), 1, 127).astype(int)

    return [
        pretty_midi.Note(
            velocity=int(smoothed[i]), pitch=n.pitch, start=n.start, end=n.end
        )
        for i, n in enumerate(notes)
    ]


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------

def _snap(t: float, grid: float, strength: float) -> float:
    nearest = round(t / grid) * grid
    return t + (nearest - t) * strength


def _estimate_clean_tempo(midi: pretty_midi.PrettyMIDI) -> float:
    """
    그리드 적합도 기반 BPM 추정.

    50–210 BPM 범위에서 1 BPM 단위로 16분음표 그리드를 시도해,
    가장 많은 온셋이 그리드±20% 이내에 떨어지는 BPM을 선택한다.
    이 방법은 estimate_tempo()가 10–30 BPM 빗나가는 경우에도 정확하게 작동한다.

    온셋이 8개 미만이면 pretty_midi 추정값으로 fallback.
    """
    all_onsets = np.array(sorted({
        n.start
        for inst in midi.instruments
        for n in inst.notes
    }))

    if len(all_onsets) < 8:
        bpm = midi.estimate_tempo()
        while bpm < 60:
            bpm *= 2
        while bpm > 200:
            bpm /= 2
        return float(round(bpm))

    best_bpm, best_score = 120.0, -1.0
    for bpm_int in range(50, 211):
        grid = 15.0 / bpm_int   # 60 / (bpm × 4) = 16분음표 길이(초)
        tol  = grid * 0.20       # ±20% 허용 오차
        res  = all_onsets % grid
        res  = np.minimum(res, grid - res)  # 그리드 경계 양쪽 오차
        score = float(np.sum(res < tol))
        if score > best_score:
            best_score = score
            best_bpm   = float(bpm_int)

    return best_bpm
