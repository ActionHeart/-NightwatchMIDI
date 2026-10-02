"""First-run source installation. Uses only the Python standard library."""
import hashlib
import os
from pathlib import Path
import struct
import subprocess
import sys


def prepare(root, run=subprocess.run):
    if sys.version_info[:2] != (3, 11) or struct.calcsize("P") != 8:
        raise RuntimeError("Please install Python 3.11 (64-bit), then run start.cmd again.")
    root = Path(root).resolve()
    environment = root / ".venv"
    python = environment / "Scripts" / "python.exe"
    marker = environment / "nightwatch-setup.sha256"
    fingerprint = hashlib.sha256((root / "pyproject.toml").read_bytes()).hexdigest()
    env = os.environ.copy()
    for key in list(env):
        if key.upper() in ("PYTHONHOME", "PYTHONPATH", "QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH"):
            del env[key]

    def execute(command, **kwargs):
        return run(command, cwd=root, env=env, **kwargs)

    if not python.is_file():
        if environment.exists():
            raise RuntimeError("The .venv folder is incomplete. Rename it and retry; no files were deleted.")
        print("First launch: creating the local Python environment...", flush=True)
        execute([sys.executable, "-I", "-m", "venv", str(environment)], check=True)
    version = execute([str(python), "-I", "-c",
                       "import sys,struct; sys.exit(0 if sys.version_info[:2]==(3,11) and struct.calcsize('P')==8 else 1)"],
                      capture_output=True)
    if version.returncode:
        raise RuntimeError("The existing .venv is not Python 3.11 (64-bit). Rename it and retry.")
    probe = [str(python), "-I", "-c",
             "from PySide6.QtWidgets import QApplication; import mido; import nightwatch_midi"]
    ready = marker.is_file() and marker.read_text(encoding="ascii").strip() == fingerprint
    if ready and execute(probe, capture_output=True).returncode == 0:
        return
    print("Installing project dependencies. Internet is required; this may take a few minutes.", flush=True)
    execute([str(python), "-I", "-m", "pip", "install", "--disable-pip-version-check", "-e", str(root)], check=True)
    execute(probe, check=True)
    marker.write_text(fingerprint, encoding="ascii")
    print("Setup complete. Starting NightwatchMIDI...", flush=True)


if __name__ == "__main__":
    try:
        prepare(Path(__file__).resolve().parents[1])
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"Setup failed: {error}\nCheck Python 3.11, internet access and folder write permissions.\n"
              "You can retry start.cmd, or download NightwatchMIDI-Windows.zip from GitHub Releases.", flush=True)
        raise SystemExit(1)
