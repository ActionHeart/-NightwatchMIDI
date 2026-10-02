"""Build an allowlisted source archive without local environments or music."""
from hashlib import sha256
from pathlib import Path
import tomllib
from zipfile import ZipFile, ZIP_DEFLATED


def main():
    root = Path(__file__).resolve().parents[1]
    version = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    files = [root / name for name in ("README.md", "LICENSE", "pyproject.toml", ".gitignore",
                                      ".gitattributes", ".python-version", "start.cmd", "start-debug.cmd", "setup.cmd")]
    for folder, suffixes in {"src/nightwatch_midi": {".py", ".json", ".ico"}, "tests": {".py", ".mid"},
                             "tools": {".py"}, "docs": {".md", ".png"},
                             "assets": {".png", ".ico"}}.items():
        files.extend(path for path in (root / folder).rglob("*") if path.is_file()
                     and path.suffix in suffixes and "__pycache__" not in path.parts)
    files.extend(root / "examples" / name for name in
                 ("README.md", "勾指起誓.mid", "卡农.mid", "小星星.mid"))
    output = root / "dist" / f"NightwatchMIDI-{version}-source.zip"
    output.parent.mkdir(exist_ok=True)
    manifest = []
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for path in sorted(set(files)):
            if path.is_symlink() or not path.resolve().is_relative_to(root):
                raise ValueError(f"Source escapes project: {path}")
            name = path.relative_to(root).as_posix()
            data = path.read_bytes()
            archive.writestr(f"NightwatchMIDI/{name}", data)
            manifest.append(f"{sha256(data).hexdigest()}  {name}")
        archive.writestr("NightwatchMIDI/RELEASE-MANIFEST.sha256", "\n".join(manifest) + "\n")
    with ZipFile(output) as archive:
        assert archive.testzip() is None
    print(f"Created {output.name}: {len(manifest)} files, {output.stat().st_size} bytes")


if __name__ == "__main__":
    main()
