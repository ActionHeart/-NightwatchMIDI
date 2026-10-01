import pytest

from nightwatch_midi.input.backend import MockInputBackend
from nightwatch_midi.mapping.plan import Action, Plan, Timing, slice_plan
from nightwatch_midi.playback.engine import PlaybackEngine


class FakeTime:
    def __init__(self):
        self.now = 0.0

    def clock(self):
        return self.now

    def wait(self, duration):
        self.now += duration
        return False


def sample_plan():
    return Plan((Action(0.0, "mouse_down", "left"),
                 Action(0.05, "key_down", "Z"),
                 Action(0.15, "key_up", "Z"),
                 Action(0.30, "key_down", "X"),
                 Action(0.40, "key_up", "X"),
                 Action(0.50, "mouse_up", "left")),
                0.6, 0, 0, 0, 0, 0, played=2, compiled_speed=1.0, timing=Timing())


def test_slice_at_zero_returns_original_plan():
    plan = sample_plan()
    assert slice_plan(plan, 0.0) is plan


def test_slice_drops_cut_note_and_restores_mouse_state():
    sliced = slice_plan(sample_plan(), 0.20)
    assert sliced.actions[0] == Action(0.0, "mouse_down", "left")
    assert [(a.kind, a.value) for a in sliced.actions] == [
        ("mouse_down", "left"), ("key_down", "X"), ("key_up", "X"), ("mouse_up", "left")]
    assert sliced.duration == pytest.approx(0.4)


def test_engine_start_at_reports_absolute_and_runs_remaining_actions():
    time = FakeTime()
    backend = MockInputBackend()
    engine = PlaybackEngine(backend, clock=time.clock, wait=time.wait)
    engine.run(slice_plan(sample_plan(), 0.20), delay=0, start_at=0.20)
    assert engine.state == "completed"
    assert engine.base == pytest.approx(0.20)
    assert engine.duration == pytest.approx(0.6)
    assert engine.position == pytest.approx(0.6)
    assert [e for e in backend.events if e[0] == "key_down"] == [("key_down", "X")]
    assert not backend.held_keys and not backend.held_buttons
