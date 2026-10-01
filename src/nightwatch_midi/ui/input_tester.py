from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QSpinBox, QPushButton, QComboBox, QPlainTextEdit,
)

from ..input.backend import MockInputBackend
from ..input.sendinput import SendInputBackend
from ..input.session import InputSession
from ..mapping.profile import load_profile
from ..game.diagnostics import capture_foreground, format_snapshot


class InputTester(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NightwatchMIDI — Phase 0 Input Tester")
        self.resize(640, 320)
        self.profile = load_profile()
        self.session = InputSession(MockInputBackend(), before_press=self.record_target)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("勾选一个或多个键/鼠标按钮进行组合测试。真实输入会发送到当前前台窗口。"))
        instructions = QLabel(
            "操作：启用真实输入 → 勾选 Z 等输入 → 点击测试 → 倒计时内切回游戏乐器界面。\n"
            "先确认手动按相同按键可以发声；仅打开本软件不会发送输入。"
        )
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        self.mode = QLabel("当前模式：Mock 模拟，不会控制游戏")
        self.mode.setStyleSheet("font-weight: bold; color: #b45f06")
        layout.addWidget(self.mode)
        self.keyboard_mode = QComboBox()
        self.keyboard_mode.addItem("键盘模式：扫描码（Scan Code）", "scan_code")
        self.keyboard_mode.addItem("键盘模式：虚拟键码（旧版发送方式）", "virtual_key")
        self.keyboard_mode.setToolTip("更改发送方式前，先关闭真实输入或点击 Emergency Stop")
        layout.addWidget(self.keyboard_mode)
        self.enable = QCheckBox("主动启用真实 Windows 输入（默认关闭）")
        self.enable.toggled.connect(self.set_real_input)
        layout.addWidget(self.enable)
        self.keys = self.add_choices(layout, self.profile.keys)
        self.buttons = self.add_choices(layout, self.profile.mouse_buttons)
        self.duration = QSpinBox()
        self.duration.setRange(1, 10000)
        self.duration.setValue(200)
        self.duration.setSuffix(" ms 持续时间")
        layout.addWidget(self.duration)
        self.delay = QSpinBox()
        self.delay.setRange(0, 30)
        self.delay.setValue(3)
        self.delay.setSuffix(" s 开始前等待（可切换目标窗口）")
        layout.addWidget(self.delay)
        self.run_button = QPushButton("测试所选输入")
        self.run_button.clicked.connect(self.run_test)
        layout.addWidget(self.run_button)
        self.stop_button = QPushButton("Emergency Stop — 释放全部输入并关闭真实输入")
        self.stop_button.clicked.connect(self.emergency_stop)
        layout.addWidget(self.stop_button)
        self.status = QLabel("Mock 模式：不会向桌面发送输入")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.diagnostics = QPlainTextEdit()
        self.diagnostics.setReadOnly(True)
        self.diagnostics.setMaximumHeight(150)
        self.diagnostics.setPlaceholderText("真实测试在按下前记录目标窗口和双方权限。测试后可选中复制此处内容。")
        layout.addWidget(self.diagnostics)
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.setInterval(5)
        self.timer.timeout.connect(self.tick)
        self.timer.timeout.connect(self.refresh_stop_style)
        self.timer.start()

    def refresh_stop_style(self):
        active = self.enable.isChecked() or self.session.deadline is not None
        style = "background: #a71930; color: white; font-weight: bold; padding: 12px" if active else ""
        if self.stop_button.styleSheet() != style:
            self.stop_button.setStyleSheet(style)

    @staticmethod
    def add_choices(layout, names):
        row = QHBoxLayout()
        choices = {}
        for name in names:
            choices[name] = QCheckBox(name)
            row.addWidget(choices[name])
        layout.addLayout(row)
        return choices

    def set_real_input(self, enabled):
        try:
            self.session.stop()
            self.session.backend = SendInputBackend(
                self.profile, keyboard_mode=self.keyboard_mode.currentData()
            ) if enabled else MockInputBackend()
            self.keyboard_mode.setEnabled(not enabled)
            self.run_button.setEnabled(True)
            self.mode.setText("当前模式：真实输入，目标为当前前台窗口" if enabled else "当前模式：Mock 模拟，不会控制游戏")
            self.status.setText(
                f"真实输入已启用；{self.keyboard_mode.currentText()}" if enabled
                else "Mock 模式：不会向桌面发送输入"
            )
        except Exception as exc:
            self.handle_error(exc)

    def run_test(self):
        keys = [k for k, box in self.keys.items() if box.isChecked()]
        buttons = [b for b, box in self.buttons.items() if box.isChecked()]
        if not keys and not buttons:
            self.status.setText("请至少选择一个输入")
            return
        try:
            self.diagnostics.setPlainText("等待按下前记录；取消倒计时则不会采集。")
            self.session.start(keys, buttons, self.duration.value() / 1000, self.delay.value())
            self.run_button.setEnabled(False)
            self.update_active_status()
        except Exception as exc:
            self.handle_error(exc)

    def record_target(self):
        if isinstance(self.session.backend, MockInputBackend):
            self.diagnostics.setPlainText("Mock 测试：未查询桌面窗口，未发送真实输入。")
            return
        try:
            self.diagnostics.setPlainText(format_snapshot(capture_foreground()))
        except Exception as exc:
            self.diagnostics.setPlainText(f"无法获取发送前诊断信息：{exc}")

    def tick(self):
        try:
            was_active = self.session.deadline is not None
            self.session.tick()
            if was_active and self.session.deadline is None:
                self.run_button.setEnabled(True)
                if isinstance(self.session.backend, MockInputBackend):
                    self.status.setText("模拟测试完成：未向 Windows 或游戏发送任何输入")
                else:
                    self.status.setText("Windows 输入调用已完成并释放；这不代表游戏已接收，请确认游戏内结果")
            elif self.session.deadline is not None:
                self.update_active_status()
        except Exception as exc:
            self.handle_error(exc)

    def update_active_status(self):
        if self.session.deadline is None:
            return
        remaining = max(0, self.session.deadline - self.session.clock())
        mode = "Mock 模拟" if isinstance(self.session.backend, MockInputBackend) else "真实输入"
        if self.session.pending is not None:
            self.status.setText(f"{mode}：{remaining:.1f} 秒后开始。真实测试请立即切回目标窗口")
        else:
            self.status.setText(f"{mode}：输入保持中，{remaining:.1f} 秒后释放")

    def emergency_stop(self):
        try:
            self.session.stop()
        except Exception as exc:
            # Preserve backend for release retries; block all new input.
            self.run_button.setEnabled(False)
            self.enable.setEnabled(False)
            self.keyboard_mode.setEnabled(False)
            self.mode.setText("输入释放失败：已阻止新测试，请重试 Emergency Stop")
            self.status.setText(f"释放失败，请重试 Emergency Stop：{exc}")
            return False
        self.session.backend = MockInputBackend()
        self.mode.setText("当前模式：Mock 模拟，不会控制游戏")
        self.enable.blockSignals(True)
        self.enable.setChecked(False)
        self.enable.blockSignals(False)
        self.enable.setEnabled(True)
        self.keyboard_mode.setEnabled(True)
        self.run_button.setEnabled(True)
        self.status.setText("已释放全部输入，真实输入已关闭")
        return True

    def handle_error(self, exc):
        if self.emergency_stop():
            self.status.setText(f"错误，输入已释放且真实输入已关闭：{exc}")

    def closeEvent(self, event):
        if self.emergency_stop():
            event.accept()
        else:
            event.ignore()
