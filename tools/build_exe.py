"""Build a standalone Windows executable with PyInstaller.

Default output is a single windowed EXE (no console) at
``dist/NightwatchMIDI.exe``. Use ``--onedir`` for a faster-starting folder
build and ``--console`` for a troubleshooting build with log output.
"""
import argparse
import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
APP_NAME = "NightwatchMIDI"

EXCLUDES = (
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtQuickWidgets",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebChannel",
    "PySide6.QtWebSockets",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtPdf",
    "PySide6.QtPdfWidgets",
    "PySide6.QtSql",
    "PySide6.QtTest",
    "PySide6.QtDesigner",
    "PySide6.QtUiTools",
    "PySide6.QtHelp",
    "PySide6.QtOpenGL",
    "PySide6.QtOpenGLWidgets",
    "tkinter",
)


def build_command(root=ROOT, *, onefile=True, console=False, icon=None):
    profiles = root / "src" / "nightwatch_midi" / "profiles"
    assets = root / "src" / "nightwatch_midi" / "assets"
    command = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--name", APP_NAME,
        "--onefile" if onefile else "--onedir",
        "--console" if console else "--windowed",
        "--paths", str(root / "src"),
        "--add-data", f"{profiles}{os.pathsep}nightwatch_midi/profiles",
    ]
    if assets.is_dir():
        command += ["--add-data", f"{assets}{os.pathsep}nightwatch_midi/assets"]
    for module in EXCLUDES:
        command += ["--exclude-module", module]
    if icon is not None:
        command += ["--icon", str(icon)]
    elif (assets / "icon.ico").is_file():
        command += ["--icon", str(assets / "icon.ico")]
    command.append(str(root / "tools" / "entry.py"))
    return command


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--onedir", action="store_true", help="folder build instead of a single EXE")
    parser.add_argument("--console", action="store_true", help="keep a console for troubleshooting")
    parser.add_argument("--icon", type=Path, help="optional .ico file for the EXE")
    args = parser.parse_args(argv)
    if importlib.util.find_spec("PyInstaller") is None:
        print('PyInstaller is missing. Install it with: pip install -e ".[packaging]"')
        return 1
    command = build_command(ROOT, onefile=not args.onedir, console=args.console, icon=args.icon)
    print("$ " + " ".join(command))
    result = subprocess.run(command, cwd=ROOT)
    if result.returncode != 0:
        return result.returncode
    target = (ROOT / "dist" / f"{APP_NAME}.exe" if not args.onedir
              else ROOT / "dist" / APP_NAME / f"{APP_NAME}.exe")
    print(f"Built: {target}")
    if not args.onedir:
        bundle = ROOT / "dist" / "NightwatchMIDI-Windows.zip"
        with ZipFile(bundle, "w", ZIP_DEFLATED) as archive:
            for path in [target, ROOT / "LICENSE", ROOT / "README.md",
                         *(ROOT / "examples" / name for name in
                           ("README.md", "勾指起誓.mid", "卡农.mid", "小星星.mid"))]:
                name = target.name if path == target else path.relative_to(ROOT).as_posix()
                archive.write(path, f"NightwatchMIDI/{name}")
        print(f"Player download: {bundle}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
