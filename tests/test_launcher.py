import importlib.util
import os
from pathlib import Path

from PySide6.QtCore import QRect, QSize

from nightwatch_midi.ui.main_window import fit_window_size

ROOT = Path(__file__).resolve().parents[1]


def load_build_exe():
    spec = importlib.util.spec_from_file_location("build_exe", ROOT / "tools" / "build_exe.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_exe_build_command_is_single_windowed_file():
    command = load_build_exe().build_command(ROOT)
    assert "--onefile" in command and "--windowed" in command
    assert ["--name", "NightwatchMIDI"] == command[command.index("--name"):command.index("--name") + 2]
    add_data = command[command.index("--add-data") + 1]
    assert add_data.endswith("nightwatch_midi/profiles")
    assert (ROOT / "src" / "nightwatch_midi" / "profiles" / "delta_harmonica.json").is_file()
    assert command[-1].endswith("entry.py")


def test_exe_build_command_supports_onedir_and_console():
    module = load_build_exe()
    command = module.build_command(ROOT, onefile=False, console=True, icon=ROOT / "app.ico")
    assert "--onedir" in command and "--console" in command
    assert "--onefile" not in command and "--windowed" not in command
    assert "--icon" in command


def test_exe_build_uses_assets_icon_when_present(tmp_path):
    (tmp_path / "src" / "nightwatch_midi" / "assets").mkdir(parents=True)
    (tmp_path / "src" / "nightwatch_midi" / "assets" / "icon.ico").write_bytes(b"ico")
    command = load_build_exe().build_command(tmp_path)
    add_data = [command[index + 1] for index, item in enumerate(command) if item == "--add-data"]
    assert any(value.endswith("nightwatch_midi/profiles") for value in add_data)
    assert any(Path(value.split(os.pathsep)[0]) == tmp_path / "src" / "nightwatch_midi" / "assets" for value in add_data)
    assert "--icon" in command
    assert Path(command[command.index("--icon") + 1]) == tmp_path / "src" / "nightwatch_midi" / "assets" / "icon.ico"


def test_window_icon_asset_and_path():
    from nightwatch_midi.__main__ import icon_path
    ico = ROOT / "src" / "nightwatch_midi" / "assets" / "icon.ico"
    assert ico.is_file(), "run tools/make_icon.py after adding assets/icon.png"
    header = ico.read_bytes()[:6]
    assert header[:4] == bytes((0, 0, 1, 0))
    assert int.from_bytes(header[4:6], "little") >= 7
    assert icon_path() == ico


def test_make_icon_builds_valid_ico_container():
    spec = importlib.util.spec_from_file_location("make_icon", ROOT / "tools" / "make_icon.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    entries = [(16, b"a" * 10), (256, b"b" * 20)]
    blob = module.build_ico(entries)
    assert blob[:6] == bytes((0, 0, 1, 0, 2, 0))
    first_width, first_height = blob[6], blob[7]
    assert (first_width, first_height) == (16, 16)
    second_width = blob[6 + 16]
    assert second_width == 0  # 256 is stored as 0
    assert blob.endswith(b"b" * 20)


def test_packaging_entry_imports_main():
    text = (ROOT / "tools" / "entry.py").read_text(encoding="utf-8")
    assert "from nightwatch_midi.__main__ import main" in text
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'packaging = ["pyinstaller>=6,<7"]' in pyproject
    assert "[project.gui-scripts]" in pyproject


def test_fit_window_size_clamps_to_small_work_area():
    assert fit_window_size(QSize(940, 620), QRect(0, 0, 1920, 1080)) == QSize(940, 620)
    assert fit_window_size(QSize(940, 620), QRect(0, 0, 800, 560)) == QSize(800, 560)
    assert fit_window_size(QSize(940, 620), QRect(0, 0, 1200, 900)) == QSize(940, 620)


def test_start_cmd_launches_without_console():
    text = (ROOT / "start.cmd").read_text(encoding="utf-8")
    assert "pythonw.exe" in text
    assert "-m nightwatch_midi" in text
    assert 'start ""' in text


def test_debug_launcher_keeps_console_for_logs():
    text = (ROOT / "start-debug.cmd").read_text(encoding="utf-8")
    assert "python.exe" in text and "-m nightwatch_midi" in text
    assert "pythonw" not in text


def test_release_whitelist_includes_both_launchers():
    text = (ROOT / "tools" / "build_source_release.py").read_text(encoding="utf-8")
    assert '"start.cmd"' in text
    assert '"start-debug.cmd"' in text
