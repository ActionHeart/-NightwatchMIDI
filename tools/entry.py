"""PyInstaller entry point: import the package and start the app."""
import sys


def smoke_test(report):
    """Verify bundled Qt and resources without enabling desktop input."""
    import json
    import traceback
    from pathlib import Path
    try:
        from PySide6.QtCore import QTimer, qVersion
        from PySide6.QtWidgets import QApplication
        from nightwatch_midi.input.sendinput import SendInputBackend

        def forbidden(*args, **kwargs):
            raise RuntimeError("Real input is forbidden during startup verification")

        SendInputBackend.__init__ = forbidden
        SendInputBackend._send = forbidden
        from nightwatch_midi.__main__ import MainWindow, icon_path
        from nightwatch_midi.input.backend import MockInputBackend
        app = QApplication([])
        window = MainWindow()
        try:
            assert isinstance(window.player.backend, MockInputBackend)
            assert icon_path().is_file() and not window.windowIcon().isNull()
            assert not window.grab().isNull()
            QTimer.singleShot(100, app.quit)
            app.exec()
        finally:
            window.emergency_stop()
            window.close()
        data = {"status": "ok", "qt": qVersion(), "platform": app.platformName()}
        code = 0
    except Exception:
        data = {"status": "error", "traceback": traceback.format_exc()}
        code = 1
    Path(report).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return code

if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--smoke-test":
        raise SystemExit(smoke_test(sys.argv[2]))
    from nightwatch_midi.__main__ import main
    raise SystemExit(main())
