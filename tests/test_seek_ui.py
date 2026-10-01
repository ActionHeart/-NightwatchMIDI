import threading
from pathlib import Path

import pytest

from nightwatch_midi.ui.midi_player import MidiPlayer


DEMO = Path(__file__).resolve().parents[1] / "tests/fixtures/twinkle_twinkle.mid"


class FakeEngine:
    """Records start arguments without running a worker thread."""

    def __init__(self, backend, before_play=None, guard=None):
        self.backend = backend
        self.done = threading.Event()
        self.base = 0.0
        self.duration = 0.0
        self.args = None
        self.error = None
        self.state = "completed"

    def start(self, plan, *, speed=1.0, delay=0.0, start_at=0.0):
        self.plan = plan
        self.base = start_at
        self.args = (plan, speed, delay, start_at)
        self.done.set()

    def stop(self, timeout=2.0):
        self.done.set()
        return True

    def retry_release(self):
        self.backend.release_all()

    @property
    def position(self):
        return self.base


def test_play_starts_from_seek_position(app, monkeypatch):
    monkeypatch.setattr("nightwatch_midi.ui.midi_player.PlaybackEngine", FakeEngine)
    player = MidiPlayer()
    player.load_file(DEMO)
    assert player.play_button.text() == "开始演奏"
    player.set_start_position(12.0)
    assert player.start_at == pytest.approx(12.0)
    assert "00:12" in player.play_button.text()
    player.play()
    plan, speed, delay, start_at = player.engine.args
    assert start_at == pytest.approx(12.0)
    assert plan.duration == pytest.approx(24.0 - 12.0, abs=0.5)
    assert player.emergency_stop()
    player.close()


def test_seek_buttons_move_idle_start(app):
    player = MidiPlayer()
    player.load_file(DEMO)
    player.seek_forward()
    assert player.start_at == pytest.approx(10.0)
    player.seek_backward()
    player.seek_backward()
    assert player.start_at == 0.0
    player.seek_backward()
    assert player.start_at == 0.0
    player.close()


def test_slider_sets_start_position_and_clears_after_load(app):
    player = MidiPlayer()
    player.load_file(DEMO)
    player.progress.setValue(500)
    assert player.start_at == pytest.approx(12.0, abs=0.2)
    player.load_file(DEMO)
    assert player.start_at == 0.0
    player.close()


def test_hotkeys_respect_toggle(app, monkeypatch):
    monkeypatch.setattr("nightwatch_midi.ui.midi_player.PlaybackEngine", FakeEngine)
    player = MidiPlayer()
    player.load_file(DEMO)
    player.hotkey_seek_forward()
    assert player.start_at == pytest.approx(10.0)
    player.hotkeys_enable.setChecked(False)
    player.hotkey_seek_forward()
    assert player.start_at == pytest.approx(10.0)
    player.hotkeys_enable.setChecked(True)
    player.set_start_position(3.0)
    player.hotkey_restart()
    assert player.start_at == pytest.approx(3.0)
    assert player.engine.args[3] == pytest.approx(3.0)
    player.close()
