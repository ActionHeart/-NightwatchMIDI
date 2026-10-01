import pytest
from PySide6.QtWidgets import QApplication
from nightwatch_midi.input.backend import MockInputBackend
from nightwatch_midi.ui.input_tester import InputTester


def test_default_mock_combination_emergency_and_close(app):
    window = InputTester()
    assert not window.enable.isChecked()
    assert window.keyboard_mode.currentData() == "scan_code"
    assert window.keyboard_mode.isEnabled()
    backend = window.session.backend
    assert isinstance(backend, MockInputBackend)
    window.keys["Z"].setChecked(True)
    window.keys["X"].setChecked(True)
    window.buttons["left"].setChecked(True)
    window.delay.setValue(0)
    window.run_button.click()
    assert backend.held_keys == {"Z", "X"}
    assert backend.held_buttons == {"left"}
    window.stop_button.click()
    assert not backend.held_keys and not backend.held_buttons
    assert not window.enable.isChecked()
    backend = window.session.backend
    window.run_button.click()
    window.close()
    assert not backend.held_keys and not backend.held_buttons


def test_release_failure_blocks_new_tests_and_allows_retry(app):
    class ReleaseFailureMock(MockInputBackend):
        fail = True
        def release_all(self):
            if self.fail:
                raise RuntimeError("Simulated release failure")
            super().release_all()
    window = InputTester()
    backend = ReleaseFailureMock()
    window.session.backend = backend
    backend.key_down("Z")
    assert not window.emergency_stop()
    assert not window.run_button.isEnabled()
    assert window.session.backend is backend
    backend.fail = False
    assert window.emergency_stop()
    assert not backend.held_keys
    window.close()


def test_mock_feedback_and_countdown(app):
    window = InputTester()
    now = [100.0]
    window.session.clock = lambda: now[0]
    window.keys["Z"].setChecked(True)
    window.delay.setValue(5)
    window.run_test()
    assert "Mock" in window.mode.text()
    assert "5.0 秒后开始" in window.status.text()
    now[0] = 103.0
    window.tick()
    assert "2.0 秒后开始" in window.status.text()
    now[0] = 105.0
    window.tick()
    assert "输入保持中" in window.status.text()
    assert "未查询桌面窗口" in window.diagnostics.toPlainText()
    now[0] = 106.0
    window.tick()
    assert "未向 Windows 或游戏发送任何输入" in window.status.text()
    window.close()
