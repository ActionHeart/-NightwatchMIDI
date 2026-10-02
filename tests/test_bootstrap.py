import hashlib
import importlib.util
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest


def load_bootstrap():
    path = Path(__file__).resolve().parents[1] / "tools" / "bootstrap.py"
    spec = importlib.util.spec_from_file_location("bootstrap", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_first_run_installs_once_and_reuses_environment(tmp_path):
    module = load_bootstrap()
    project = tmp_path / "中文 folder with spaces"
    project.mkdir()
    (project / "pyproject.toml").write_text("project-v1")
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        assert kwargs["cwd"] == project
        if "venv" in command:
            executable = project / ".venv/Scripts/python.exe"
            executable.parent.mkdir(parents=True)
            executable.touch()
        return SimpleNamespace(returncode=0)

    module.prepare(project, run)
    assert sum("venv" in cmd for cmd in calls) == 1
    assert sum("pip" in cmd for cmd in calls) == 1
    assert calls[-2][-1] == str(project)
    calls.clear()
    module.prepare(project, run)
    assert all("pip" not in cmd and "venv" not in cmd for cmd in calls)
    (project / "pyproject.toml").write_text("project-v2")
    module.prepare(project, run)
    assert sum("pip" in cmd for cmd in calls) == 1


def test_install_failure_never_marks_environment_ready(tmp_path):
    module = load_bootstrap()
    (tmp_path / "pyproject.toml").write_text("test")
    python = tmp_path / ".venv/Scripts/python.exe"
    python.parent.mkdir(parents=True)
    python.touch()

    def run(command, **kwargs):
        if "pip" in command:
            raise subprocess.CalledProcessError(1, command)
        return SimpleNamespace(returncode=0)

    with pytest.raises(subprocess.CalledProcessError):
        module.prepare(tmp_path, run)
    assert not (tmp_path / ".venv/nightwatch-setup.sha256").exists()


def test_incomplete_environment_is_preserved(tmp_path):
    module = load_bootstrap()
    (tmp_path / "pyproject.toml").write_text("test")
    environment = tmp_path / ".venv"
    environment.mkdir()
    saved = environment / "keep.txt"
    saved.write_text("keep")
    with pytest.raises(RuntimeError, match="incomplete"):
        module.prepare(tmp_path, lambda *a, **k: pytest.fail("Must not run subprocess"))
    assert saved.read_text() == "keep"
