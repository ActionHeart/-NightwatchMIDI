"""Create a public-domain melody and a profile-range test MIDI; sends no input."""
from pathlib import Path
import mido


def save(path, notes):
    mid = mido.MidiFile(type=1, ticks_per_beat=480)
    mid.tracks.append(mido.MidiTrack([mido.MetaMessage("set_tempo", tempo=500000)]))
    track = mido.MidiTrack([mido.MetaMessage("track_name", name=path.stem)])
    mid.tracks.append(track)
    for pitch, beats in notes:
        track.append(mido.Message("note_on", note=pitch, velocity=80, time=0))
        track.append(mido.Message("note_off", note=pitch, velocity=0, time=int(beats * 480 - 40)))
        track.append(mido.MetaMessage("text", text="", time=40))
    mid.save(path)


if __name__ == "__main__":
    target = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
    target.mkdir(exist_ok=True)
    a = [60, 60, 67, 67, 69, 69, 67, 65, 65, 64, 64, 62, 62, 60]
    b = [67, 67, 65, 65, 64, 64, 62, 67, 67, 65, 65, 64, 64, 62]
    melody = a + b + a
    save(target / "twinkle_twinkle.mid", [(n, 2 if i % 7 == 6 else 1) for i, n in enumerate(melody)])
    save(target / "chromatic_48_85.mid", [(n, 1) for n in range(48, 86)])
    print("Created twinkle_twinkle.mid (24 seconds) and chromatic_48_85.mid (19 seconds)")
