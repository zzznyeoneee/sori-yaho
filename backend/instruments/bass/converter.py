"""Bass audio → MIDI → MusicXML 변환 파이프라인."""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# 베이스 음역대: E1(28) ~ G3(55)
BASS_PITCH_MIN = 28
BASS_PITCH_MAX = 55

# General MIDI 베이스 계열 프로그램 번호(0-indexed 32~39):
# Acoustic/Fingered/Picked/Fretless/Slap/Synth Bass
_BASS_GM_PROGRAMS = range(32, 40)
# mt3-infer 0.1.3의 "mr_mt3"·"mt3_pytorch"는 둘 다 vendored T5 모델이
# transformers.GenerationMixin을 명시적으로 상속하지 않아, 현재 배포된
# 어떤 transformers 버전(4.49 / 4.57.5 / 5.x 모두 재현 시도)에서도
# model.generate() 호출 시 깨진다 (mt3_pytorch는 그 전에 vendored
# t5.py가 transformers.models.t5.modeling_t5에서 이미 제거된
# `checkpoint` 심볼을 import하다가 ImportError로 먼저 죽는다).
#
# "yourmt3"는 HF generate()를 쓰지 않고 자체 autoregressive 디코딩
# (task_cond_dec_generate)을 구현해 이 문제를 구조적으로 피해간다.
# 체크포인트 저장소가 커서(git-lfs로 huggingface.co/spaces/mimbres/YourMT3
# 전체 clone, 체크포인트 5종 포함 수 GB) 다운로드는 오래 걸리지만
# 셋 중 실제로 동작할 가능성이 가장 높아 이걸 사용한다.
_MT3_MODEL = "yourmt3"
_MT3_SAMPLE_RATE = 16000


def _patch_transformers_compat() -> None:
    """mt3-infer 0.1.3의 vendored 모델 코드가 이미 제거된 옛 transformers
    심볼을 import하다가 죽는 것을 우회한다. 둘 다 학습/멀티GPU 전용
    기능이라 추론 경로에서는 실제로 호출되지 않는다.

    - transformers.models.t5.modeling_t5.checkpoint: gradient checkpointing
      함수가 클래스 기반(GradientCheckpointingLayer)으로 리팩토링되며 사라짐.
    - transformers.utils.model_parallel_utils: 레거시 naive 모델 병렬화
      유틸리티 모듈 자체가 삭제됨 (yourmt3의 t5mod.py가 import).
    - transformers.pytorch_utils.find_pruneable_heads_and_indices: 레거시
      어텐션 헤드 프루닝 유틸리티가 삭제됨 (perceiver_mod.py가 import).
      추론 시 실제 프루닝을 수행하지 않으므로 원본 구현을 그대로 복원해도
      무해하다.
    - PreTrainedModel.get_head_mask/_convert_head_mask_to_5d: T5/Perceiver
      인코더가 head_mask=None을 표준 형식([None]*num_layers)으로 바꾸는 데
      쓰는 ModuleUtilsMixin 메서드가 삭제됨. head_mask를 실제로 넘기지
      않는(None) 추론 경로에서도 이 변환 자체가 필수라 no-op 스텁이 아니라
      원본 구현을 그대로 복원해야 한다.
    """
    import sys
    import types
    import torch
    import transformers.models.t5.modeling_t5 as t5_modeling
    import transformers.pytorch_utils as pytorch_utils
    from transformers.modeling_utils import PreTrainedModel

    if not hasattr(t5_modeling, "checkpoint"):
        t5_modeling.checkpoint = torch.utils.checkpoint.checkpoint

    if "transformers.utils.model_parallel_utils" not in sys.modules:
        stub = types.ModuleType("transformers.utils.model_parallel_utils")
        stub.assert_device_map = lambda *a, **k: None
        stub.get_device_map = lambda n_layers, devices: {d: [] for d in devices}
        sys.modules["transformers.utils.model_parallel_utils"] = stub

    if not hasattr(pytorch_utils, "find_pruneable_heads_and_indices"):
        def find_pruneable_heads_and_indices(heads, n_heads, head_size, already_pruned_heads):
            mask = torch.ones(n_heads, head_size)
            heads = set(heads) - already_pruned_heads
            for head in heads:
                head = head - sum(1 if h < head else 0 for h in already_pruned_heads)
                mask[head] = 0
            mask = mask.view(-1).eq(1)
            index = torch.arange(len(mask))[mask].long()
            return heads, index
        pytorch_utils.find_pruneable_heads_and_indices = find_pruneable_heads_and_indices

    if not hasattr(PreTrainedModel, "get_head_mask"):
        def _convert_head_mask_to_5d(self, head_mask, num_hidden_layers):
            if head_mask.dim() == 1:
                head_mask = head_mask.unsqueeze(0).unsqueeze(0).unsqueeze(-1).unsqueeze(-1)
                head_mask = head_mask.expand(num_hidden_layers, -1, -1, -1, -1)
            elif head_mask.dim() == 2:
                head_mask = head_mask.unsqueeze(1).unsqueeze(-1).unsqueeze(-1)
            head_mask = head_mask.to(dtype=self.dtype)
            return head_mask

        def get_head_mask(self, head_mask, num_hidden_layers, is_attention_chunked=False):
            if head_mask is not None:
                head_mask = self._convert_head_mask_to_5d(head_mask, num_hidden_layers)
                if is_attention_chunked is True:
                    head_mask = head_mask.unsqueeze(-1)
            else:
                head_mask = [None] * num_hidden_layers
            return head_mask

        PreTrainedModel._convert_head_mask_to_5d = _convert_head_mask_to_5d
        PreTrainedModel.get_head_mask = get_head_mask


def audio_to_midi(audio_path: str, output_dir: str) -> str:
    """MT3(mt3-infer)로 베이스 WAV → MIDI 변환."""
    import librosa
    import pretty_midi

    _patch_transformers_compat()
    from mt3_infer import transcribe

    audio_path = Path(audio_path)
    output_dir = Path(output_dir)

    logger.info("MT3 베이스 채보 시작: %s", audio_path)

    y, _ = librosa.load(str(audio_path), sr=_MT3_SAMPLE_RATE, mono=True)
    raw_midi_mido = transcribe(y, sr=_MT3_SAMPLE_RATE, model=_MT3_MODEL)

    # mt3-infer는 mido.MidiFile을 반환한다 (pretty_midi 객체가 아님).
    # note/instrument 단위로 다루기 위해 임시 저장 후 pretty_midi로 재로드한다.
    mt3_raw_path = output_dir / "mt3_raw.mid"
    raw_midi_mido.save(str(mt3_raw_path))
    raw_midi = pretty_midi.PrettyMIDI(str(mt3_raw_path))

    # 베이스 GM 프로그램 트랙을 우선 채택 (MT3는 다중 악기를 동시에 채보하므로
    # 프로그램 번호로 베이스 트랙만 골라내야 한다). 매칭되는 트랙이 없으면
    # 전체 트랙에서 베이스 음역대로 필터링해 대체한다.
    bass_notes = [
        note
        for inst in raw_midi.instruments
        if not inst.is_drum and inst.program in _BASS_GM_PROGRAMS
        for note in inst.notes
    ]
    if not bass_notes:
        logger.warning("MT3 결과에 베이스 GM 트랙이 없어 음역대 필터로 대체합니다.")
        bass_notes = [
            note
            for inst in raw_midi.instruments
            if not inst.is_drum
            for note in inst.notes
        ]

    # 베이스 음역대 밖 음표 제거
    bass_midi = pretty_midi.PrettyMIDI(initial_tempo=raw_midi.estimate_tempo())
    instrument = pretty_midi.Instrument(program=33, name="Bass")  # Electric Bass
    instrument.notes = sorted(
        (n for n in bass_notes if BASS_PITCH_MIN <= n.pitch <= BASS_PITCH_MAX),
        key=lambda n: n.start,
    )
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
