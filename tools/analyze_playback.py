"""Read local MIDI files and summarize plans; never constructs a real backend."""
from collections import Counter
import json
from pathlib import Path

from nightwatch_midi.mapping.plan import build_plan, TIMINGS
from nightwatch_midi.mapping.melody import rank_melodies
from nightwatch_midi.mapping.profile import load_profile
from nightwatch_midi.midi.parser import read_midi


def summarize(path):
    song = read_midi(path)
    profile = load_profile(name="delta_harmonica.json")
    candidate = rank_melodies(song, profile)[0]
    plan = build_plan(song, profile, track=candidate.track, channel=candidate.channel,
                      timing=TIMINGS["stable"], trim_leading=True)
    held, durations = {}, []
    for action in plan.actions:
        if action.kind == "key_down":
            held[action.value] = action.time
        elif action.kind == "key_up":
            durations.append(action.time - held.pop(action.value))
    streams = []
    for track, channel in sorted({(n.track, n.channel) for n in song.notes}):
        notes = [n for n in song.notes if n.track == track and n.channel == channel]
        streams.append({"track": track, "channel": channel + 1, "name": song.track_names[track],
                        "notes": len(notes), "range": [min(n.pitch for n in notes), max(n.pitch for n in notes)],
                        "start": round(min(n.start for n in notes), 3),
                        "short_notes_30ms": sum(n.end - n.start < 0.03 for n in notes)})
    variants = []
    for speed in (1.0, 0.8, 0.6, 0.5, 0.25):
        alternative = build_plan(song, profile, track=candidate.track, channel=candidate.channel,
                                 timing=TIMINGS["stable"], trim_leading=True, speed=speed)
        variants.append({"speed": speed, "played": alternative.played, "density_dropped": alternative.density_dropped})
    return {"file": path.name, "duration": round(song.duration, 3), "notes": len(song.notes),
            "skipped": plan.skipped, "simplified": plan.simplified, "key_presses": len(durations),
            "key_presses_under_30ms": sum(d < 0.03 for d in durations), "streams": streams,
            "suggested_track": candidate.track + 1, "suggested_channel": candidate.channel + 1,
            "folded": plan.folded, "density_dropped": plan.density_dropped,
            "max_shift_ms": round(plan.max_shift * 1000, 3), "play_duration": round(plan.duration, 3),
            "minimum_hold_ms": round(min(durations, default=0) * 1000, 3), "speed_variants": variants}


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    report = []
    for path in sorted((root / "examples").glob("*.mid")):
        try:
            report.append(summarize(path))
        except Exception as exc:
            report.append({"file": path.name, "error": str(exc)})
    target = root / "artifacts/playback_analysis_after.json"
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True, indent=2))
