from pathlib import Path

from PySide6.QtWidgets import QScrollArea

from nightwatch_midi.input.backend import MockInputBackend
from nightwatch_midi.ui.main_window import MainWindow
from nightwatch_midi.ui.midi_player import MidiPlayer
from nightwatch_midi.ui.safety_shortcut import SafetyShortcut


DEMO = Path(__file__).resolve().parents[1] / "tests/fixtures/twinkle_twinkle.mid"


def test_main_actions_fit_and_pages_switch(app):
    window = MainWindow()
    window.show()
    window.player.load_file(DEMO)
    app.processEvents()
    assert window.height() <= 650
    assert window.width() <= 1000
    p = window.player
    assert p.tabs.count() == 4
    assert p.tabs.currentWidget() is p.play_page
    assert not p.advanced.isVisible() and not p.library_list.isVisible()
    assert not p.track.isVisible()
    assert not p.profile_button.isVisible()
    assert not window.tester.isVisible()
    assert p.input_mode.currentText() == "预览模式"
    assert isinstance(p.backend, MockInputBackend)
    for widget in (p.open_button, p.optimize_button, p.input_mode, p.play_button, p.stop_button):
        assert widget.isVisible()
        point = widget.mapTo(window, widget.rect().bottomRight())
        assert window.rect().contains(point)
        parent = widget.parentWidget()
        while parent is not window:
            assert not isinstance(parent, QScrollArea)
            parent = parent.parentWidget()
    p.tabs.setCurrentWidget(p.library_page)
    app.processEvents()
    assert p.library_list.isVisible() and not p.advanced.isVisible()
    assert window.height() <= 650
    p.tabs.setCurrentWidget(p.score_page)
    app.processEvents()
    assert p.score_editor.isVisible()
    assert window.height() <= 650 and window.width() <= 1000
    p.tabs.setCurrentWidget(p.advanced_page)
    app.processEvents()
    assert p.advanced.isVisible() and p.advanced.count() == 4
    assert window.height() <= 650
    p.tabs.setCurrentWidget(p.play_page)
    app.processEvents()
    assert p.play_button.isVisible() and p.stop_button.isVisible()
    window.close()


def test_disclaimer_banner_present(app):
    from nightwatch_midi.ui.main_window import DISCLAIMER_TEXT
    window = MainWindow()
    window.show()
    app.processEvents()
    assert window.disclaimer.objectName() == "disclaimer"
    assert "账号封禁风险" in window.disclaimer.text()
    assert "封" in DISCLAIMER_TEXT and "自行承担" in DISCLAIMER_TEXT
    assert "QPushButton#disclaimer" in window.styleSheet()
    assert window.height() <= 650
    window.close()


def test_startup_disclaimer_dialog_buttons(app):
    from nightwatch_midi.ui.main_window import DISCLAIMER_ACCEPT, DISCLAIMER_DECLINE, disclaimer_box
    window = MainWindow()
    startup = disclaimer_box(window, startup=True)
    assert {button.text() for button in startup.buttons()} == {DISCLAIMER_ACCEPT, DISCLAIMER_DECLINE}
    assert "封禁" in startup.informativeText()
    startup.close()
    banner = disclaimer_box(window)
    assert {button.text() for button in banner.buttons()} == {"关闭"}
    banner.close()
    window.close()


def test_confirm_disclaimer_accept_and_decline(app):
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from nightwatch_midi.ui.main_window import (DISCLAIMER_ACCEPT, DISCLAIMER_DECLINE,
                                                confirm_disclaimer)

    def click(label):
        def handler():
            dialog = QApplication.activeModalWidget() or QApplication.activeWindow()
            for button in dialog.buttons():
                if button.text() == label:
                    button.click()
                    return
            raise AssertionError(f"button not found: {label}")
        return handler

    window = MainWindow()
    QTimer.singleShot(0, click(DISCLAIMER_ACCEPT))
    assert confirm_disclaimer(window) is True
    QTimer.singleShot(0, click(DISCLAIMER_DECLINE))
    assert confirm_disclaimer(window) is False
    window.close()


def test_header_instrument_menu_and_gear(app):
    window = MainWindow()
    assert window.instrument.text().startswith("守夜人口琴")
    actions = [action.text() for action in window.instrument.menu().actions()]
    assert actions == ["导入乐器配置（JSON）…", "打开设置…"]
    assert not window.settings_button.icon().isNull()
    window.close()


def test_range_modes_and_optimization_keep_preview(app):
    p = MidiPlayer()
    p.load_file(DEMO)
    assert p.track.currentData() is not None
    assert p.file_label.text() == DEMO.name
    original_metadata = p.file_info.text()
    p.range_mode.setCurrentIndex(p.range_mode.findData("original"))
    assert p.transpose.value() == 0 and not p.fold.isChecked()
    p.transpose.setValue(12)
    assert p.range_mode.currentData() == "custom"
    p.optimize()
    assert p.range_mode.currentData() == "auto" and p.fold.isChecked()
    assert p.file_info.text() == original_metadata
    assert isinstance(p.backend, MockInputBackend)
    assert not p.enable.isChecked()
    p.basic_speed.setCurrentIndex(p.basic_speed.findData(1.5))
    assert p.plan.compiled_speed == 1.5
    p.speed.setValue(.35)
    assert p.basic_speed.currentData() == .35
    p.basic_delay.setCurrentIndex(0)
    assert p.delay.value() == 0
    p.close()


def test_file_placeholder_then_loaded_name(app):
    p = MidiPlayer()
    assert p.file_label.text() == "尚未选择乐谱"
    assert p.file_label.property("empty") == "true"
    assert "--" in p.file_info.text()
    assert not p.play_button.isEnabled()
    assert not p.optimize_button.isEnabled()
    p.load_file(DEMO)
    assert p.file_label.text() == DEMO.name
    assert p.file_label.property("empty") == "false"
    assert p.play_button.isEnabled() and p.optimize_button.isEnabled()
    p.close()


def test_settings_escape_releases_test_input(app):
    window = MainWindow()
    window.open_settings()
    window.settings_dialog.open_tester()
    tester = window.tester
    backend = tester.session.backend
    backend.key_down("Z")
    window.settings_dialog.tester_dialog.reject()
    assert not backend.held_keys
    assert not tester.enable.isChecked()
    assert not window.settings_dialog.tester_dialog.isVisible()
    window.close()


def test_failed_release_keeps_dialog_open(app, monkeypatch):
    window = MainWindow()
    window.open_settings()
    window.settings_dialog.open_tester()
    dialog = window.settings_dialog.tester_dialog
    backend = window.tester.session.backend
    def fail():
        raise RuntimeError("release failed")
    with monkeypatch.context() as patch:
        patch.setattr(backend, "release_all", fail)
        dialog.reject()
        assert dialog.isVisible()
        assert not window.tester.run_button.isEnabled()
    window.close()


def test_f12_uses_injected_reader_and_releases_all(app):
    window = MainWindow()
    p = window.player
    p.load_file(DEMO)
    p.play()
    engine = p.engine
    backend = p.backend
    shortcut = SafetyShortcut(window, window.is_active, window.emergency_stop, reader=lambda: True)
    shortcut.poll()
    assert engine.done.is_set()
    assert p.engine is None
    assert not backend.held_keys and not backend.held_buttons
    assert p.input_mode.currentData() is False
    assert not p.stop_button.styleSheet()
    window.close()


def test_game_mode_failure_returns_to_preview(app, monkeypatch):
    p = MidiPlayer()
    def unavailable(*args, **kwargs):
        raise OSError("test backend unavailable")
    monkeypatch.setattr("nightwatch_midi.ui.midi_player.SendInputBackend", unavailable)
    p.input_mode.setCurrentIndex(1)
    assert isinstance(p.backend, MockInputBackend)
    assert not p.enable.isChecked() and p.input_mode.currentData() is False
    assert "test backend unavailable" in p.status.text()
    assert not p.stop_button.styleSheet()
    p.close()
