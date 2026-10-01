"""Local song library: keep a copy of imported MIDI files for quick reuse."""
import json
import os
import shutil
from datetime import datetime
from pathlib import Path


def default_root():
    override = os.environ.get("NIGHTWATCH_MIDI_HOME")
    base = Path(override) if override else Path(os.environ.get("APPDATA") or Path.home()) / "NightwatchMIDI"
    return base / "library"


class SongLibrary:
    """Copy imported MIDI files into a managed folder and index them in JSON."""

    def __init__(self, root=None):
        self.root = Path(root) if root else default_root()
        self.index_path = self.root / "library.json"
        self.entries = self._read()

    def _read(self):
        try:
            data = json.loads(self.index_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        if not isinstance(data, list):
            return []
        return [self._normalize(item) for item in data
                if isinstance(item, dict) and item.get("file") and item.get("title")]

    @staticmethod
    def _normalize(item):
        entry = dict(item)
        entry.setdefault("original", "")
        entry.setdefault("added", "")
        entry.setdefault("favorite", False)
        entry.setdefault("last_played", None)
        entry.setdefault("play_count", 0)
        entry.setdefault("meta", {})
        entry.setdefault("optimized", None)
        return entry

    def _write(self):
        self.root.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self.entries, ensure_ascii=False, indent=2)
        temp = self.index_path.with_suffix(".tmp")
        temp.write_text(payload, encoding="utf-8")
        temp.replace(self.index_path)

    def find(self, path):
        resolved = Path(path).resolve()
        for entry in self.entries:
            stored = (self.root / entry["file"]).resolve()
            original = entry.get("original")
            if stored == resolved or (original and Path(original).resolve() == resolved):
                return entry
        return None

    def contains(self, path):
        return self.find(path) is not None

    def songs(self):
        found = []
        for entry in self.entries:
            path = self.root / entry["file"]
            if path.is_file():
                found.append({**entry, "path": path})
        return sorted(found, key=lambda item: item["title"].casefold())

    def add(self, path, meta=None):
        source = Path(path)
        existing = self.find(source)
        if existing:
            if meta:
                existing.setdefault("meta", {}).update(meta)
                self._write()
            return existing
        self.root.mkdir(parents=True, exist_ok=True)
        target = self._unique_target(source.name)
        shutil.copy2(source, target)
        entry = {
            "title": source.name,
            "file": target.name,
            "original": str(source.resolve()),
            "added": datetime.now().isoformat(timespec="seconds"),
            "favorite": False,
            "last_played": None,
            "play_count": 0,
            "meta": meta or {},
            "optimized": None,
        }
        self.entries.append(entry)
        self._write()
        return entry

    def update(self, path, **fields):
        entry = self.find(path)
        if entry is None:
            return None
        entry.update(fields)
        self._write()
        return entry

    def mark_played(self, path, meta=None):
        entry = self.find(path)
        if entry is None:
            return None
        entry["last_played"] = datetime.now().isoformat(timespec="seconds")
        entry["play_count"] = int(entry.get("play_count", 0)) + 1
        if meta:
            entry.setdefault("meta", {}).update(meta)
        self._write()
        return entry

    def set_optimized(self, path, summary):
        data = dict(summary)
        data.setdefault("at", datetime.now().isoformat(timespec="seconds"))
        return self.update(path, optimized=data)

    def remove(self, path):
        entry = self.find(path)
        if entry is None:
            return False
        try:
            (self.root / entry["file"]).unlink(missing_ok=True)
        except OSError:
            pass
        self.entries.remove(entry)
        self._write()
        return True

    def _unique_target(self, name):
        stem, suffix = Path(name).stem, Path(name).suffix
        candidate = Path(name)
        counter = 2
        while (self.root / candidate).exists():
            candidate = Path(f"{stem} ({counter}){suffix}")
            counter += 1
        return self.root / candidate
