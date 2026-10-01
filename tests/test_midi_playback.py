import threading

import mido
import pytest

from nightwatch_midi.input.backend import MockInputBackend
from nightwatch_midi.mapping.profile import load_profile, Binding
from nightwatch_midi.mapping.plan import Action, Plan, build_plan
from nightwatch_midi.midi.parser import Note, Song, parse_midi, read_midi
from nightwatch_midi.playback.engine import PlaybackEngine


def midi(*tracks, kind=1):
    mid = mido.MidiFile(type=kind, ticks_per_beat=480)
    mid.tracks.extend(mido.MidiTrack(track) for track in tracks)
    return mid


def test_tempo_changes_track_merge_and_velocity_zero(tmp_path):
    mid = midi([
        mido.MetaMessage("set_tempo", tempo=500000),
        mido.MetaMessage("set_tempo", tempo=1000000, time=480),
    ], [mido.MetaMessage("track_name", name="Melody"),
        mido.Message("note_on", note=60, velocity=70),
        mido.Message("note_on", note=60, velocity=0, time=960)])
    path = tmp_path / "tempo.mid"
    mid.save(path)
    song = read_midi(path)
    assert song.duration == pytest.approx(1.5)
    assert song.notes == (Note(0, 60, 0, 1.5, 1, 0, 70),)
    assert song.track_names[1] == "Melody"


def test_sustain_and_overlapping_same_pitch():
    song = parse_midi(midi([
        mido.Message("control_change", control=64, value=127),
        mido.Message("note_on", note=60, velocity=80),
        mido.Message("note_on", note=60, velocity=70, time=120),
        mido.Message("note_off", note=60, time=120),
        mido.Message("note_off", note=60, time=120),
        mido.Message("control_change", control=64, value=0, time=120),
    ]))
    assert len(song.notes) == 2
    assert [n.start for n in song.notes] == [0, 0.125]
    assert [n.end for n in song.notes] == [0.5, 0.5]


def test_unclosed_note_and_type2_rejection():
    song = parse_midi(midi([mido.Message("note_on", note=60),
                            mido.MetaMessage("end_of_track", time=480)]))
    assert song.notes[0].end == 0.5
    assert song.warnings
    with pytest.raises(ValueError, match="Type 2"):
        parse_midi(midi([], kind=2))
    mid = midi([])
    mid.ticks_per_beat = -24
    with pytest.raises(ValueError, match="SMPTE"):
        parse_midi(mid)


def test_profile_matches_complete_reference_table():
    profile = load_profile(name="delta_harmonica.json")
    assert set(map(int, profile.midi_notes)) == set(range(48, 86))
    expected_keys = ["Z", "Z", "X", "X", "C", "V", "V", "B", "B", "N", "N", "M"]
    for base, octave_buttons in [(48, ("left",)), (60, ())]:
        for offset, key in enumerate(expected_keys):
            buttons = octave_buttons + (("middle",) if offset in (1, 3, 6, 8, 10) else ())
            assert profile.binding(base + offset) == Binding(key, buttons)
    assert profile.binding(72) == Binding(",")
    assert profile.binding(73) == Binding(",", ("middle",))
    for offset in range(2, 12):
        buttons = ("right",) + (("middle",) if offset in (3, 6, 8, 10) else ())
        assert profile.binding(72 + offset) == Binding(expected_keys[offset], buttons)
    assert profile.binding(84) == Binding(",", ("right",))
    assert profile.binding(85) == Binding(",", ("right", "middle"))


def song_for(pitches):
    return Song(tuple(Note(i, p, i * 0.5, (i + 1) * 0.5, 0, 0, 80) for i, p in enumerate(pitches)), len(pitches) * 0.5, ("Melody",))


def test_mapping_modifiers_before_key_and_release_before_switch():
    plan = build_plan(song_for([48, 61, 84]), load_profile(name="delta_harmonica.json"))
    assert [(a.kind, a.value) for a in plan.actions[:2]] == [("mouse_down", "left"), ("key_down", "Z")]
    assert plan.actions[1].time - plan.actions[0].time >= plan.timing.lead - 1e-9
    off, mod_up, mod_down, on = plan.actions[2:6]
    assert [a.kind for a in (off, mod_up, mod_down, on)] == ["key_up", "mouse_up", "mouse_down", "key_down"]
    assert mod_up.time - off.time >= plan.timing.tail - 1e-9
    assert on.time - mod_down.time >= plan.timing.lead - 1e-9
    assert [(a.kind, a.value) for a in plan.actions[-2:]] == [("key_up", ","), ("mouse_up", "right")]


def test_repeat_note_retriggers():
    plan = build_plan(song_for([60, 60]), load_profile(name="delta_harmonica.json"))
    assert [a.kind for a in plan.actions] == ["key_down", "key_up", "key_down", "key_up"]


def test_note_gap_preserves_onsets_and_short_notes():
    plan = build_plan(song_for([60, 60]), load_profile(name="delta_harmonica.json"), note_gap=0.02)
    assert plan.actions[2].time - plan.actions[0].time == pytest.approx(0.5)
    assert plan.actions[2].time - plan.actions[1].time == pytest.approx(0.02)
    tiny = Song((Note(0, 60, 0, 0.01, 0, 0, 80),), 0.01, ("A",))
    plan = build_plan(tiny, load_profile(name="delta_harmonica.json"), note_gap=0.02)
    assert plan.actions[-1].time - plan.actions[0].time >= plan.timing.hold - 1e-9


def test_entire_demo_song_with_fake_clock():
    from pathlib import Path
    song = read_midi(Path(__file__).resolve().parents[1] / "tests/fixtures/twinkle_twinkle.mid")
    assert len(song.notes) == 42
    assert song.duration == pytest.approx(24)
    time = FakeTime()
    backend = MockInputBackend()
    plan = build_plan(song, load_profile(name="delta_harmonica.json"))
    engine = PlaybackEngine(backend, clock=time.clock, wait=time.wait)
    engine.run(plan, delay=5)
    assert engine.state == "completed"
    assert len([e for e in backend.events if e[0] == "key_down"]) == 42
    assert time.now == pytest.approx(129 + plan.timing.lead)
    assert plan.skipped == plan.simplified == 0
    assert not backend.held_keys and not backend.held_buttons


def test_track_channel_drums_transpose_and_octave_fold():
    profile = load_profile(name="delta_harmonica.json")
    song = Song((Note(0, 36, 0, 1, 0, 0, 80), Note(1, 60, 0, 1, 1, 9, 80)), 1, ("A", "Drum"))
    assert build_plan(song, profile, fold=False).skipped == 1
    plan = build_plan(song, profile, fold=True)
    assert plan.folded == 1 and plan.selected == 1
    assert plan.actions[0].value == "left"
    assert build_plan(song, profile, transpose=12).skipped == 0
    assert build_plan(song, profile, track=1).actions == ()
    assert build_plan(song, profile, channel=9, exclude_drums=False).mapped == 1


def test_compatible_chords_and_conflicting_mouse_modes():
    profile = load_profile(name="delta_harmonica.json")
    song = Song(tuple(Note(i, p, 0, 1, 0, 0, 80) for i, p in enumerate([60, 64, 67])), 1, ("A",))
    assert build_plan(song, profile).simplified == 2
    plan = build_plan(song, profile, chords=True)
    assert plan.simplified == 0
    assert {a.value for a in plan.actions if a.kind == "key_down"} == {"Z", "C", "B"}
    conflict = Song(song.notes + (Note(3, 75, 0, 1, 0, 0, 80),), 1, ("A",))
    plan = build_plan(conflict, profile, chords=True)
    assert plan.simplified == 3
    assert [a.value for a in plan.actions if a.kind == "key_down"] == ["X"]


class FakeTime:
    def __init__(self):
        self.now = 100.0

    def clock(self):
        return self.now

    def wait(self, duration):
        self.now += duration
        return False


def test_absolute_schedule_does_not_accumulate_backend_latency():
    time = FakeTime()
    observed = []

    class SlowMock(MockInputBackend):
        def key_down(self, key):
            observed.append(time.now)
            super().key_down(key)
            time.now += 0.03

    backend = SlowMock()
    plan = build_plan(song_for([60, 62, 64]), load_profile(name="delta_harmonica.json"), speed=2)
    engine = PlaybackEngine(backend, clock=time.clock, wait=time.wait)
    engine.run(plan, speed=2, delay=1)
    assert observed == pytest.approx([101.025, 101.275, 101.525])
    assert time.now == pytest.approx(101.775)
    assert engine.state == "completed" and engine.done.is_set()
    assert not backend.held_keys and backend.events[-1] == ("release_all", "")


def test_cancel_while_holding_modifier_and_key():
    time = FakeTime()
    backend = MockInputBackend()
    engine = PlaybackEngine(backend, clock=time.clock)

    def wait(duration):
        if backend.held_keys:
            assert backend.held_keys == {"Z"} and backend.held_buttons == {"left"}
            engine.cancel.set()
            return True
        return time.wait(duration)

    engine._wait = wait
    engine.run(build_plan(song_for([48]), load_profile(name="delta_harmonica.json")), delay=0)
    assert engine.state == "stopped"
    assert not backend.held_keys and not backend.held_buttons


def test_input_exception_and_release_failure_retry():
    class FaultMock(MockInputBackend):
        fail_release = True

        def key_down(self, key):
            super().key_down(key)
            raise RuntimeError("down failed")

        def release_all(self):
            if self.fail_release:
                raise RuntimeError("up failed")
            super().release_all()

    backend = FaultMock()
    engine = PlaybackEngine(backend)
    engine.run(build_plan(song_for([48]), load_profile(name="delta_harmonica.json")), delay=0)
    assert engine.state == "error" and engine.release_failed
    assert isinstance(engine.error, BaseExceptionGroup)
    backend.fail_release = False
    engine.retry_release()
    assert not backend.held_keys and not backend.held_buttons and not engine.release_failed


def test_worker_countdown_cancels_without_real_sleep():
    backend = MockInputBackend()
    engine = PlaybackEngine(backend)
    engine.start(build_plan(song_for([60]), load_profile(name="delta_harmonica.json")), delay=30)
    assert engine.stop(timeout=1)
    assert engine.done.is_set() and engine.state == "stopped"
    assert not any(event[0] == "key_down" for event in backend.events)


def test_focus_guard_stops_and_releases():
    time = FakeTime()
    backend = MockInputBackend()
    engine = PlaybackEngine(backend, clock=time.clock, wait=time.wait, guard=lambda: not backend.held_keys)
    engine.run(build_plan(song_for([48]), load_profile(name="delta_harmonica.json")), delay=0)
    assert engine.state == "error"
    assert not backend.held_keys and not backend.held_buttons


def test_cancel_thread_with_held_note():
    held = threading.Event()

    class HeldMock(MockInputBackend):
        def key_down(self, key):
            super().key_down(key)
            held.set()

    backend = HeldMock()
    song = Song((Note(0, 48, 0, 30, 0, 0, 80),), 30, ("A",))
    engine = PlaybackEngine(backend)
    engine.start(build_plan(song, load_profile(name="delta_harmonica.json")), delay=0)
    assert held.wait(1)
    assert engine.stop(1)
    assert not backend.held_keys and not backend.held_buttons
