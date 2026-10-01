from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QKeySequence, QPainter, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QToolButton, QMenu,
)

DISCLAIMER_BRIEF = ("免责声明：使用可能违反游戏规则，存在账号封禁风险，请自行承担后果。")
DISCLAIMER_TEXT = (
    "本项目采用 MIT 许可证，允许使用、修改与商业使用，请保留版权和许可声明。\n\n"
    "本软件通过模拟键盘与鼠标输入在游戏内演奏，可能违反游戏的用户协议或相关规定；"
    "使用本软件存在账号被警告、限制、回滚或封禁的风险，也可能因误操作、系统延迟、后台负载或兼容性问题导致异常。"
    "上述风险及后果需由使用者自行承担。\n\n"
    "请在使用前确认游戏规则与当地法律法规，并自行评估风险；继续使用即表示已理解并接受本声明。"
)
DISCLAIMER_ACCEPT = "我已知晓，继续使用"
DISCLAIMER_DECLINE = "退出"


def fit_window_size(desired, available):
    """Shrink the desired size so it fits the available screen work area."""
    return QSize(min(desired.width(), available.width()),
                 min(desired.height(), available.height()))


def disclaimer_box(parent=None, *, startup=False):
    box = QMessageBox(parent)
    box.setWindowTitle("免责声明")
    box.setIcon(QMessageBox.Icon.Warning)
    box.setText("使用前请阅读并确认以下声明")
    from html import escape
    box.setTextFormat(Qt.TextFormat.RichText)
    risk = "使用本软件存在账号被警告、限制、回滚或封禁的风险"
    formatted = escape(DISCLAIMER_TEXT).replace("\n\n", "<br><br>")
    box.setInformativeText(formatted.replace(risk, f'<b style="color:#b91c1c">{risk}</b>'))
    if startup:
        box.addButton(DISCLAIMER_ACCEPT, QMessageBox.ButtonRole.AcceptRole)
        box.addButton(DISCLAIMER_DECLINE, QMessageBox.ButtonRole.RejectRole)
    else:
        box.addButton("关闭", QMessageBox.ButtonRole.AcceptRole)
    return box


def confirm_disclaimer(parent=None):
    """Startup gate: True only when the user accepts the disclaimer."""
    box = disclaimer_box(parent, startup=True)
    box.exec()
    clicked = box.clickedButton()
    accepted = clicked is not None and box.buttonRole(clicked) == QMessageBox.ButtonRole.AcceptRole
    box.deleteLater()
    return accepted

from .input_tester import InputTester
from .midi_player import MidiPlayer
from .player_view import STYLE
from .settings_dialog import SettingsDialog
from .safety_shortcut import SafetyShortcut
from ..resources import icon_path


def gear_icon(size=18, color="#4a5a70"):
    """Draw a gear so the icon never depends on font coverage."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(color))
    center = size / 2
    outer, inner, hole = size * 0.45, size * 0.28, size * 0.12
    painter.translate(center, center)
    for index in range(8):
        painter.save()
        painter.rotate(index * 45)
        painter.drawRoundedRect(QRectF(-size * 0.09, -outer, size * 0.18,
                                       outer - inner + size * 0.12), 1.4, 1.4)
        painter.restore()
    painter.drawEllipse(QPointF(0, 0), inner, inner)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
    painter.drawEllipse(QPointF(0, 0), hole, hole)
    painter.end()
    return QIcon(pixmap)


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowIcon(QIcon(str(icon_path())))
        self.setObjectName("mainWindow")
        self.setWindowTitle("NightwatchMIDI — 守夜人口琴 MIDI播放器")
        self.setStyleSheet(STYLE)
        self.resize(940, 620)
        screen = QApplication.primaryScreen()
        if screen is not None and QApplication.platformName() != "offscreen":
            self.resize(fit_window_size(self.size(), screen.availableGeometry()))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 6, 18, 6)
        header = QHBoxLayout()
        heading = QVBoxLayout()
        title = QLabel("NightwatchMIDI")
        title.setObjectName("title")
        heading.addWidget(title)
        subtitle = QLabel("三角洲行动 · 守夜人口琴 MIDI播放器")
        subtitle.setObjectName("muted")
        heading.addWidget(subtitle)
        header.addLayout(heading, 1)
        self.instrument = QToolButton()
        self.instrument.setObjectName("instrument")
        self.instrument.setText("守夜人口琴  ▼")
        self.instrument.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.instrument.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.instrument.setToolTip("当前乐器：守夜人口琴；点击导入其他乐器配置")
        menu = QMenu(self.instrument)
        menu.addAction("导入乐器配置（JSON）…", self.player_action("choose_profile"))
        menu.addAction("打开设置…", self.open_settings)
        self.instrument.setMenu(menu)
        header.addWidget(self.instrument)
        self.settings_button = QPushButton()
        self.settings_button.setObjectName("gear")
        self.settings_button.setIcon(gear_icon())
        self.settings_button.setIconSize(QSize(18, 18))
        self.settings_button.setFixedWidth(38)
        self.settings_button.setToolTip("设置（乐器 / 诊断 / 输入测试）")
        self.settings_button.clicked.connect(self.open_settings)
        header.addWidget(self.settings_button)
        layout.addLayout(header)
        self.player = MidiPlayer()
        layout.addWidget(self.player, 1)
        self.disclaimer = QPushButton(DISCLAIMER_BRIEF)
        self.disclaimer.setObjectName("disclaimer")
        self.disclaimer.setCursor(Qt.CursorShape.PointingHandCursor)
        self.disclaimer.setToolTip("点击查看完整免责声明")
        self.disclaimer.setFixedHeight(26)
        self.disclaimer.clicked.connect(self.show_disclaimer)
        layout.addWidget(self.disclaimer)
        self.tester = InputTester()
        self.settings_dialog = SettingsDialog(self)
        self.shortcut = QShortcut(QKeySequence("F12"), self)
        self.shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self.shortcut.activated.connect(self.emergency_stop)
        self.safety = SafetyShortcut(self, self.is_active, self.emergency_stop,
                                     hotkeys=self.player.global_hotkeys())

    def player_action(self, name):
        # QMenu actions are created before self.player exists; resolve lazily.
        return lambda: getattr(self.player, name)()

    def is_active(self):
        return bool(self.player.engine or self.player.enable.isChecked() or
                    self.tester.enable.isChecked() or self.tester.session.deadline is not None)

    def show_disclaimer(self):
        disclaimer_box(self).exec()

    def open_settings(self):
        if self.emergency_stop():
            self.settings_dialog.show()

    def emergency_stop(self):
        player_ok = self.player.emergency_stop()
        tester_ok = self.tester.emergency_stop()
        return player_ok and tester_ok

    def closeEvent(self, event):
        if self.emergency_stop():
            self.settings_dialog.close()
            event.accept()
        else:
            event.ignore()
