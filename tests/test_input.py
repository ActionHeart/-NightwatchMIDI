import json

import pytest
from nightwatch_midi.input.backend import InputBackend, MockInputBackend
from nightwatch_midi.input.session import InputSession
from nightwatch_midi.mapping.profile import load_profile


def test_abstract_backend():
    with pytest.raises(TypeError):
        InputBackend()


def test_combination_and_absolute_deadline():
    now = [100.0]
    backend = MockInputBackend()
    session = InputSession(backend, lambda: now[0])
    session.start(["Z", "X"], ["left", "middle", "right"], 0.2, 3)
    now[0] = 102.9
    session.tick()
    assert not backend.held_keys
    now[0] = 103.0
    session.tick()
    assert backend.held_keys == {"Z", "X"}
    assert backend.held_buttons == {"left", "middle", "right"}
    now[0] = 103.19
    session.tick()
    assert backend.held_keys
    now[0] = 110.0  # Late UI tick still releases immediately.
    session.tick()
    assert not backend.held_keys and not backend.held_buttons
    assert session.deadline is None


@pytest.mark.parametrize("delay", [0, 3])
def test_stop_cancels_active_and_pending(delay):
    backend = MockInputBackend()
    now = [0.0]
    session = InputSession(backend, lambda: now[0])
    session.start(["Z"], ["left"], 2, delay)
    session.stop()
    now[0] = 100
    session.tick()
    session.stop()
    assert not backend.held_keys and not backend.held_buttons
    assert session.pending is None and session.deadline is None


def test_partial_failure_releases_all():
    class FailingMock(MockInputBackend):
        def mouse_down(self, button):
            super().mouse_down(button)
            raise RuntimeError("Simulated failure after down")
    backend = FailingMock()
    session = InputSession(backend)
    with pytest.raises(RuntimeError):
        session.start(["Z"], ["left"], 1)
    assert not backend.held_keys and not backend.held_buttons
    assert backend.events[-1] == ("release_all", "")


@pytest.mark.parametrize("duration", [0, -1, float("nan"), float("inf")])
def test_bad_duration(duration):
    with pytest.raises(ValueError):
        InputSession(MockInputBackend()).start(["Z"], [], duration)


def test_profile_is_source_of_bindings(tmp_path):
    profile = load_profile()
    assert list(profile.keys) == list("ZXCVBNM,")
    assert profile.midi_notes == {}
    path = tmp_path / "custom.json"
    path.write_text(json.dumps({"name": "Custom", "keys": {"A": 65}, "mouse_buttons": [], "midi_notes": {"60": "A"}}))
    assert load_profile(path).midi_notes == {"60": "A"}


def test_invalid_profile(tmp_path):
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps({"name": "Bad", "keys": {"Z": 999}, "mouse_buttons": [], "midi_notes": {}}))
    with pytest.raises(ValueError):
        load_profile(path)
