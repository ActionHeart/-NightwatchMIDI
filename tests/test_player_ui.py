import threading
from types import SimpleNamespace

import mido
import pytest
from PySide6.QtWidgets import QApplication

from nightwatch_midi.ui.main_window import MainWindow
from nightwatch_midi.ui.midi_player import MidiPlayer
from nightwatch_midi.input.backend import MockInputBackend
from nightwatch_midi.mapping.plan import Plan


def test_file_to_player_and_stop(app, tmp_path):
    mid = mido.MidiFile()
    mid.tracks.append(mido.MidiTrack([mido.Message("note_on", note=49),
                                      mido.Message("note_off", note=49, time=480)]))
    path = tmp_path / "test.mid"
    mid.save(path)
    player = MidiPlayer()
    player.load_file(path)
    assert not player.enable.isChecked()
    assert isinstance(player.backend, MockInputBackend)
    assert player.plan.mapped == 1 and player.play_button.isEnabled()
    backend = player.backend
    player.play()
    assert not player.open_button.isEnabled()
    assert player.tabs.currentWidget() is player.play_page
    assert not player.tabs.isTabEnabled(player.tabs.indexOf(player.library_page))
    assert not player.tabs.isTabEnabled(player.tabs.indexOf(player.score_page))
    assert not player.tabs.isTabEnabled(player.tabs.indexOf(player.advanced_page))
    assert player.emergency_stop()
    assert not backend.held_keys and not backend.held_buttons
    assert player.play_button.isEnabled()
    assert player.tabs.isTabEnabled(player.tabs.indexOf(player.library_page))
    assert player.tabs.isTabEnabled(player.tabs.indexOf(player.score_page))
    assert player.tabs.isTabEnabled(player.tabs.indexOf(player.advanced_page))
    player.close()


def test_main_window_switch_cancels_playback(app):
    window = MainWindow()
    player = window.player
    from nightwatch_midi.mapping.plan import Action
    player.plan = Plan((Action(0, "key_down", "Z"), Action(1, "key_up", "Z")), 1, 1, 1, 0, 0, 0)
    player.play()
    engine = player.engine
    window.open_settings()
    window.settings_dialog.open_tester()
    assert engine.done.is_set()
    assert not window.tester.enable.isChecked() and not player.enable.isChecked()
    assert player.engine is None
    window.close()


def test_completed_mock_updates_ui_without_desktop_access(app):
    from nightwatch_midi.playback.engine import PlaybackEngine
    player = MidiPlayer()
    player.engine = PlaybackEngine(player.backend, before_play=player._before_play, guard=player._guard)
    player.engine.run(Plan((), 0, 0, 0, 0, 0, 0), delay=0)
    player.poll()
    assert "整曲预览完成" in player.status.text()
    assert "未访问真实桌面" in player.diagnostics.toPlainText()
    assert not player.enable.isChecked()
    player.close()


def test_player_rebuilds_physical_timeline_on_speed_change(app):
    from nightwatch_midi.midi.parser import Song, Note
    player = MidiPlayer()
    player.song = Song((Note(0, 48, 0, 0.1, 0, 0, 80),), 0.1, ("Melody",))
    player.rebuild()
    player.speed.setValue(2)
    assert player.plan.compiled_speed == 2
    assert player.plan.timing.hold == 0.05
    player.timing_preset.setCurrentIndex(player.timing_preset.findData("standard"))
    assert player.plan.timing.hold == 0.035
    assert player.note_gap.value() == 25
    assert player.fold.isChecked() and not player.enable.isChecked()
    player.close()


def test_countdown_uses_big_label_page(app):
    from nightwatch_midi.midi.parser import Note, Song
    player = MidiPlayer()
    player.song = Song((Note(0, 48, 0, 0.1, 0, 0, 80),), 0.1, ("Melody",))
    player.rebuild()
    player.engine = SimpleNamespace(state="countdown", origin=105.0, clock=lambda: 100.0,
                                    done=threading.Event(), base=0.0)
    player.poll()
    assert player.progress_header.currentIndex() == 1
    assert player.countdown_label.text() == "5"
    assert "秒后开始" in player.status.text()
    player.engine = None
    player.close()


def test_recommend_octave_and_speed_are_mock_only(app):
    from nightwatch_midi.midi.parser import Song, Note
    player = MidiPlayer()
    player.song = Song(tuple(Note(i, 90 + i % 3, i * 0.08, i * 0.08 + 0.04, 0, 0, 80)
                             for i in range(12)), 1, ("Melody",))
    player.rebuild()
    player.suggest_octave()
    assert player.transpose.value() == -12
    assert player.plan.folded == 0
    player.suggest_speed()
    assert player.speed.value() <= 1
    assert player.plan.density_dropped == 0
    assert isinstance(player.backend, MockInputBackend)
    player.close()
