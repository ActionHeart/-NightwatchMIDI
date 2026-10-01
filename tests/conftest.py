import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"

import pytest
from nightwatch_midi.input.sendinput import SendInputBackend


@pytest.fixture(scope="session")
def app():
    from PySide6.QtWidgets import QApplication
    application = QApplication.instance() or QApplication([])
    yield application
    application.processEvents()


@pytest.fixture(autouse=True)
def isolate_song_library(monkeypatch, tmp_path):
    monkeypatch.setenv("NIGHTWATCH_MIDI_HOME", str(tmp_path / "home"))


@pytest.fixture(autouse=True)
def forbid_real_input(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Real Windows input is forbidden in pytest")
    monkeypatch.setattr(SendInputBackend, "__init__", forbidden)
    monkeypatch.setattr(SendInputBackend, "_send", forbidden)
    # Unit tests use synthetic diagnostic data, never inspect the live desktop.
    monkeypatch.setattr("nightwatch_midi.game.diagnostics._dll", forbidden)
    monkeypatch.setattr("nightwatch_midi.ui.safety_shortcut.f12_down", forbidden)
    monkeypatch.setattr("nightwatch_midi.ui.safety_shortcut.key_down", forbidden)
