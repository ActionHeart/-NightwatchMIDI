import mido
import pytest
from pathlib import Path

from nightwatch_midi.input.backend import MockInputBackend
from nightwatch_midi.mapping.melody import rank_melodies
from nightwatch_midi.mapping.plan import build_plan, TIMINGS
from nightwatch_midi.mapping.profile import load_profile
from nightwatch_midi.midi.parser import Note, Song, parse_midi, decode_track_name, read_midi
from nightwatch_midi.playback.engine import PlaybackEngine


def make_song(pitches, spacing=0.2, length=0.3):
    notes = tuple(Note(i, p, i * spacing, i * spacing + length, 0, 0, 80) for i, p in enumerate(pitches))
    return Song(notes, max(n.end for n in notes), ("Test",))


def check_margins(events, timing):
    held = {}
    last_up = last_mouse = float("-inf")
    buttons = set()
    for time, kind, value in events:
        if kind == "key_down":
            assert value not in held
            assert time - last_mouse >= timing.lead - 1e-8
            assert time - last_up >= timing.gap - 1e-8
            held[value] = time
        elif kind == "key_up":
            assert time - held.pop(value) >= timing.hold - 1e-8
            last_up = time
        elif kind.startswith("mouse_"):
            assert not held, "Modifier changed under a held note"
            assert time - last_up >= timing.tail - 1e-8
            if kind == "mouse_down":
                buttons.add(value)
            else:
                buttons.remove(value)
            last_mouse = time
    assert not held and not buttons


@pytest.mark.parametrize("preset", list(TIMINGS))
@pytest.mark.parametrize("speed", [0.5, 1.0, 2.0])
def test_physical_margins_survive_speed_and_dense_notes(preset, speed):
    profile = load_profile(name="delta_harmonica.json")
    plan = build_plan(make_song([48, 61, 84, 49, 60, 60], spacing=0.06, length=0.015),
                      profile, speed=speed, timing=TIMINGS[preset], density="complete")
    check_margins([(a.time, a.kind, a.value) for a in plan.actions], plan.timing)
    assert plan.played == 6
    assert plan.density_dropped == 0


def test_no_resurrection_after_higher_note_finishes():
    song = Song((Note(0, 60, 0, 3, 0, 0, 80), Note(1, 72, 1, 1.3, 0, 0, 80)), 3, ("A",))
    plan = build_plan(song, load_profile(name="delta_harmonica.json"))
    assert [a.value for a in plan.actions if a.kind == "key_down"] == ["Z", ","]


def test_octave_fold_does_not_promote_bass_above_melody():
    song = Song((Note(0, 70, 0, 1, 0, 0, 90), Note(1, 86, 0, 1, 0, 0, 70)), 1, ("A",))
    profile = load_profile(name="delta_harmonica.json")
    plan = build_plan(song, profile)
    assert plan.folded == 1
    assert [a.value for a in plan.actions if a.kind == "key_down"] == [profile.binding(74).key]


def test_rhythm_drops_excess_density_instead_of_unbounded_delay():
    song = make_song([48, 61] * 30, spacing=0.02, length=0.01)
    profile = load_profile(name="delta_harmonica.json")
    rhythm = build_plan(song, profile, timing=TIMINGS["stable"], onset_window=0)
    complete = build_plan(song, profile, timing=TIMINGS["stable"], density="complete", onset_window=0)
    assert rhythm.density_dropped > 0
    assert rhythm.max_shift <= 0.060 + 1e-9
    assert complete.played == 60 and complete.density_dropped == 0
    assert complete.max_shift > 1
    check_margins([(a.time, a.kind, a.value) for a in rhythm.actions], rhythm.timing)


def test_humanized_chord_groups_attacks_without_chaining_entire_phrase():
    song = Song((Note(0, 48, 0, 1, 0, 0, 80), Note(1, 60, 0.02, 1, 0, 0, 80),
                 Note(2, 64, 0.04, 1, 0, 0, 80)), 1, ("A",))
    plan = build_plan(song, load_profile(name="delta_harmonica.json"), density="complete")
    assert plan.simplified == 1
    assert plan.played == 2
    assert [a.value for a in plan.actions if a.kind == "key_down"] == ["Z", "C"]


def test_sustain_same_channel_notes_pair_with_their_own_track():
    mid = mido.MidiFile(type=1, ticks_per_beat=480)
    mid.tracks.extend([
        mido.MidiTrack([mido.Message("note_on", note=60), mido.Message("note_off", note=60, time=960)]),
        mido.MidiTrack([mido.Message("note_on", note=60, time=240), mido.Message("note_off", note=60, time=240)]),
    ])
    song = parse_midi(mid)
    assert [(n.track, n.start, n.end) for n in song.notes] == [(0, 0, 1), (1, 0.25, 0.5)]


def test_track_label_decoding_and_stream_recommendation():
    assert decode_track_name("钢琴".encode("gbk").decode("latin1")) == "钢琴"
    notes = [Note(i, 60 + i % 8, i * 0.5, i * 0.5 + 0.3, 0, 2, 80) for i in range(20)]
    notes += [Note(100 + i, 38, i * 0.5, i * 0.5 + 0.3, 1, 0, 80) for i in range(20)]
    notes += [Note(200 + i, 70, i * 0.5, i * 0.5 + 0.3, 2, 9, 80) for i in range(20)]
    ranked = rank_melodies(Song(tuple(notes), 10, ("Melody", "Bass", "Drums")), load_profile(name="delta_harmonica.json"))
    assert (ranked[0].track, ranked[0].channel) == (0, 2)
    assert all(c.channel != 9 for c in ranked)


def test_realized_wait_jitter_does_not_collapse_lead_or_hold():
    now, events = [0.0], []

    class TimestampMock(MockInputBackend):
        def key_down(self, key):
            events.append((now[0], "key_down", key))
            super().key_down(key)
        def key_up(self, key):
            events.append((now[0], "key_up", key))
            super().key_up(key)
        def mouse_down(self, key):
            events.append((now[0], "mouse_down", key))
            super().mouse_down(key)
        def mouse_up(self, key):
            events.append((now[0], "mouse_up", key))
            super().mouse_up(key)

    def wait(seconds):
        now[0] += seconds + 0.004  # Simulate OS wake-up overshoot.
        return False

    plan = build_plan(make_song([48, 61, 84], spacing=0.5), load_profile(name="delta_harmonica.json"), timing=TIMINGS["stable"])
    engine = PlaybackEngine(TimestampMock(), clock=lambda: now[0], wait=wait)
    engine.run(plan, delay=0)
    assert engine.state == "completed"
    check_margins(events, plan.timing)


def test_large_scheduler_stall_stops_instead_of_catchup_burst():
    now = [0.0]
    def wait(seconds):
        now[0] += seconds + 1
        return False
    backend = MockInputBackend()
    engine = PlaybackEngine(backend, clock=lambda: now[0], wait=wait)
    engine.run(build_plan(make_song([60, 62]), load_profile(name="delta_harmonica.json")), delay=0)
    assert engine.state == "error" and "250 ms" in str(engine.error)
    assert not backend.held_keys
    assert not any(kind == "key_down" for kind, _ in backend.events)


def test_cancel_during_modifier_lead_releases_mouse():
    backend = MockInputBackend()
    engine = PlaybackEngine(backend)
    def wait(seconds):
        assert backend.held_buttons == {"left"} and not backend.held_keys
        engine.cancel.set()
        return True
    engine._wait = wait
    engine.run(build_plan(make_song([48]), load_profile(name="delta_harmonica.json")), delay=0)
    assert engine.state == "stopped" and not backend.held_buttons


def test_speed_mismatch_requires_recompile_and_releases():
    backend = MockInputBackend()
    engine = PlaybackEngine(backend)
    engine.run(build_plan(make_song([60]), load_profile(name="delta_harmonica.json")), speed=2, delay=0)
    assert engine.state == "error"
    assert backend.events[-1] == ("release_all", "")


@pytest.mark.parametrize("path", sorted((Path(__file__).resolve().parents[1] / "examples").glob("*.mid")), ids=lambda p: p.stem)
def test_local_midi_complete_mock_run_and_margin_audit(path):
    song = read_midi(path)
    profile = load_profile(name="delta_harmonica.json")
    choice = rank_melodies(song, profile)[0]
    plan = build_plan(song, profile, track=choice.track, channel=choice.channel,
                      timing=TIMINGS["stable"], trim_leading=True)
    check_margins([(a.time, a.kind, a.value) for a in plan.actions], plan.timing)
    assert plan.selected == plan.simplified + plan.skipped + plan.played + plan.density_dropped
    now = [0.0]
    def wait(seconds):
        now[0] += seconds
        return False
    backend = MockInputBackend()
    engine = PlaybackEngine(backend, clock=lambda: now[0], wait=wait)
    engine.run(plan, delay=0)
    assert engine.state == "completed", engine.error
    assert not backend.held_keys and not backend.held_buttons
    assert sum(kind == "key_down" for kind, _ in backend.events) == plan.played
