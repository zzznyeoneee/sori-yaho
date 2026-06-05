"""Convert drum MIDI to MusicXML notation."""
from music21 import converter
from pathlib import Path


def midi_to_drum_score(midi_path: str, output_dir: str) -> str:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    score = converter.parse(midi_path)
    out_path = output_dir / f"{Path(midi_path).stem}.xml"
    score.write("musicxml", fp=str(out_path))
    return str(out_path)
