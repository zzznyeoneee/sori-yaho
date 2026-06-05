"""Convert drum MIDI to MusicXML notation."""
from music21 import converter, stream, note, meter, tempo as m21tempo
from pathlib import Path
import pretty_midi


def midi_to_drum_score(midi_path: str, output_dir: str) -> str:
    """
    midi_path:   드럼 MIDI 파일 경로
    output_dir:  결과 저장 폴더
    반환값:      생성된 .xml 파일 절대 경로
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    score = converter.parse(midi_path)
    out_path = output_dir / f"{Path(midi_path).stem}.xml"
    score.write("musicxml", fp=str(out_path))
    return str(out_path)
