"""Inspect tempo/meter metadata without sending input."""
import json
from pathlib import Path
import mido

root = Path(__file__).resolve().parents[1]
(root / "artifacts").mkdir(exist_ok=True)
rows = []
for path in sorted((root / "examples").glob("*.mid")):
    mid = mido.MidiFile(path)
    tempo, meter = [], []
    for track in mid.tracks:
        tick = 0
        for msg in track:
            tick += msg.time
            if msg.type == "set_tempo":
                tempo.append((tick, round(60000000 / msg.tempo, 3)))
            elif msg.type == "time_signature":
                meter.append((tick, msg.numerator, msg.denominator))
    rows.append({"file": path.name, "ppqn": mid.ticks_per_beat, "tempo_events": len(tempo),
                 "bpm_range": [min(v for _, v in tempo), max(v for _, v in tempo)] if tempo else [120, 120],
                 "tempo_start": sorted(tempo)[:8], "meters": sorted(meter)})
(root / "artifacts/midi_meter.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(rows, ensure_ascii=True, indent=2))
