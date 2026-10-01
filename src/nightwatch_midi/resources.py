"""Resources installed alongside the Python package, also usable when frozen."""
from pathlib import Path


def icon_path() -> Path:
    return Path(__file__).resolve().parent / "assets" / "icon.ico"
