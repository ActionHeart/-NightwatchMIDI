import atexit
import os
import signal
import sys

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont, QIcon
from .ui.main_window import MainWindow, confirm_disclaimer
from .resources import icon_path


def main() -> int:
    # 启动脚本使用 pythonw，无控制台；这里同时压低窗口几何类平台警告。
    os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.window=false;qt.qpa.windows=false")
    app = QApplication(sys.argv)
    app.setFont(QFont("Microsoft YaHei UI", 9))
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("NightwatchMIDI")
        except Exception:
            pass
    icon = icon_path()
    if icon is not None:
        app.setWindowIcon(QIcon(str(icon)))
    window = MainWindow()
    cleanup = window.emergency_stop
    atexit.register(cleanup)
    app.aboutToQuit.connect(cleanup)
    previous_hook = sys.excepthook

    def exception_hook(kind, value, traceback):
        cleanup()
        previous_hook(kind, value, traceback)

    sys.excepthook = exception_hook
    old_signals = {}

    def quit_signal(*_):
        if cleanup():
            app.quit()

    for name in ("SIGINT", "SIGTERM", "SIGBREAK"):
        if hasattr(signal, name):
            sig = getattr(signal, name)
            old_signals[sig] = signal.signal(sig, quit_signal)
    try:
        if not confirm_disclaimer(window):
            return 0
        window.show()
        return app.exec()
    finally:
        cleanup()
        atexit.unregister(cleanup)
        sys.excepthook = previous_hook
        for sig, handler in old_signals.items():
            signal.signal(sig, handler)


if __name__ == "__main__":
    raise SystemExit(main())
