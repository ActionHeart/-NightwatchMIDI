"""UI-owned F12 stop and playback hotkeys, including when the game is foreground.

Reads current key state only; sends no input, injects nothing and installs no hook.
"""
import ctypes
import sys

from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import QApplication

VK_F8, VK_F9, VK_F10, VK_F12 = 0x77, 0x78, 0x79, 0x7B


def key_down(vk):
    # Only inspect the current key-down bit, not the unreliable historical bit:
    # https://learn.microsoft.com/windows/win32/api/winuser/nf-winuser-getasynckeystate
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    function = user32.GetAsyncKeyState
    function.argtypes = [ctypes.c_int]
    function.restype = ctypes.c_short
    return bool(function(vk) & 0x8000)


def f12_down():
    return key_down(VK_F12)


class SafetyShortcut(QObject):
    def __init__(self, parent, active, stop, reader=None, hotkeys=None, key_reader=None):
        super().__init__(parent)
        self.active, self.stop = active, stop
        self.reader = reader
        self.hotkeys = dict(hotkeys or {})
        self.key_reader = key_reader
        # Headless previews/tests never query the real desktop.
        real_desktop = sys.platform == "win32" and QApplication.platformName() == "windows"
        if self.reader is None and real_desktop:
            self.reader = f12_down
        if self.key_reader is None and self.hotkeys and real_desktop:
            self.key_reader = key_down
        self.pressed = False
        self.key_pressed = {vk: False for vk in self.hotkeys}
        self.timer = QTimer(self)
        self.timer.setInterval(25)
        self.timer.timeout.connect(self.poll)
        self.timer.start()

    def _reset(self):
        self.pressed = False
        for vk in self.key_pressed:
            self.key_pressed[vk] = False

    def poll(self):
        if not self.active():
            self._reset()
            return
        if self.reader is not None:
            try:
                down = self.reader()
            except Exception:
                self.stop()
                return
            if down and not self.pressed:
                self.stop()
            self.pressed = down
        if self.key_reader is None:
            return
        for vk, callback in self.hotkeys.items():
            try:
                down = self.key_reader(vk)
            except Exception:
                self.stop()
                return
            if down and not self.key_pressed[vk]:
                try:
                    callback()
                except Exception:
                    pass
            self.key_pressed[vk] = down
