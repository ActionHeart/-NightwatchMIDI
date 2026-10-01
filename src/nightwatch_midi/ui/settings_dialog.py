from PySide6.QtWidgets import QDialog, QVBoxLayout, QTabWidget, QWidget, QLabel, QPushButton, QScrollArea


class SafeDialog(QDialog):
    """Include Escape/reject as well as the window close button in cleanup."""
    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.setModal(True)

    def done(self, result):
        if self.owner.emergency_stop():
            super().done(result)

    def closeEvent(self, event):
        if self.owner.emergency_stop():
            event.accept()
        else:
            event.ignore()


class SettingsDialog(SafeDialog):
    def __init__(self, owner):
        super().__init__(owner)
        self.setWindowTitle("NightwatchMIDI · 设置")
        self.resize(760, 520)
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        layout.addWidget(tabs)
        instrument = QWidget()
        form = QVBoxLayout(instrument)
        for widget in (owner.player.profile_label, owner.player.profile_button):
            form.addWidget(widget)
            widget.show()
        form.addWidget(QLabel("乐器配置包含音高、按键和鼠标组合。导入后默认使用预览模式。"))
        self.profile_result = QLabel("")
        self.profile_result.setWordWrap(True)
        form.addWidget(self.profile_result)
        form.addStretch()
        tabs.addTab(instrument, "乐器")
        advanced = QWidget()
        advanced_layout = QVBoxLayout(advanced)
        self.test_button = QPushButton("输入测试")
        self.test_button.clicked.connect(self.open_tester)
        advanced_layout.addWidget(self.test_button)
        advanced_layout.addWidget(QLabel("播放诊断（出错时可复制反馈）"))
        advanced_layout.addWidget(owner.player.diagnostics)
        owner.player.diagnostics.show()
        tabs.addTab(advanced, "高级")
        close = QPushButton("返回演奏")
        close.clicked.connect(self.reject)
        layout.addWidget(close)
        self.tester_dialog = SafeDialog(owner)
        self.tester_dialog.setWindowTitle("NightwatchMIDI · 输入测试")
        self.tester_dialog.resize(780, 600)
        tester_layout = QVBoxLayout(self.tester_dialog)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(owner.tester)
        tester_layout.addWidget(scroll)
        self.finished.connect(lambda: self.tester_dialog.close())
        owner.player.profile_button.clicked.connect(self.update_instrument)

    def update_instrument(self):
        name = self.owner.player.profile_label.text().split("：", 1)[-1]
        self.owner.instrument.setText(f"{name}  ▼")
        self.profile_result.setText(self.owner.player.status.text())

    def open_tester(self):
        if self.owner.emergency_stop():
            self.tester_dialog.show()

    def closeEvent(self, event):
        super().closeEvent(event)
        if event.isAccepted():
            self.tester_dialog.close()
