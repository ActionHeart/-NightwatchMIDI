import mido
import pytest

from nightwatch_midi.library import SongLibrary


def make_midi(path, note=60):
    path.parent.mkdir(parents=True, exist_ok=True)
    mid = mido.MidiFile()
    mid.tracks.append(mido.MidiTrack([mido.Message("note_on", note=note),
                                      mido.Message("note_off", note=note, time=480)]))
    mid.save(path)
    return path


def test_add_copies_and_persists(tmp_path):
    source = make_midi(tmp_path / "song.mid")
    library = SongLibrary(tmp_path / "library")
    entry = library.add(source)
    assert entry["title"] == "song.mid"
    assert (tmp_path / "library" / entry["file"]).is_file()
    assert library.contains(source)
    reopened = SongLibrary(tmp_path / "library")
    assert [item["title"] for item in reopened.songs()] == ["song.mid"]


def test_add_same_source_is_idempotent(tmp_path):
    source = make_midi(tmp_path / "song.mid")
    library = SongLibrary(tmp_path / "library")
    first = library.add(source)
    second = library.add(source)
    assert first == second
    assert len(library.songs()) == 1
    assert len(list((tmp_path / "library").glob("*.mid"))) == 1


def test_duplicate_names_get_unique_files(tmp_path):
    first = make_midi(tmp_path / "one" / "song.mid", note=60)
    second = make_midi(tmp_path / "two" / "song.mid", note=62)
    library = SongLibrary(tmp_path / "library")
    first_entry = library.add(first)
    second_entry = library.add(second)
    assert first_entry["file"] != second_entry["file"]
    assert len(library.songs()) == 2


def test_missing_files_are_hidden(tmp_path):
    source = make_midi(tmp_path / "song.mid")
    library = SongLibrary(tmp_path / "library")
    entry = library.add(source)
    (tmp_path / "library" / entry["file"]).unlink()
    assert library.songs() == []


def test_broken_index_is_treated_as_empty(tmp_path):
    root = tmp_path / "library"
    root.mkdir()
    (root / "library.json").write_text("{not json", encoding="utf-8")
    assert SongLibrary(root).songs() == []


def test_favorite_play_and_optimization_metadata(tmp_path):
    source = make_midi(tmp_path / "song.mid")
    library = SongLibrary(tmp_path / "library")
    library.add(source, meta={"duration": 1.25, "notes": 2, "bpm": "120.0"})
    assert library.songs()[0]["favorite"] is False
    library.update(source, favorite=True)
    library.mark_played(source)
    library.set_optimized(source, {"transpose": -12, "folded": 1, "density_dropped": 2, "speed": 1.0})
    entry = SongLibrary(tmp_path / "library").songs()[0]
    assert entry["favorite"] is True
    assert entry["play_count"] == 1 and entry["last_played"]
    assert entry["meta"]["notes"] == 2
    assert entry["optimized"]["transpose"] == -12
    assert entry["optimized"]["at"]


def test_remove_deletes_copy_and_entry(tmp_path):
    source = make_midi(tmp_path / "song.mid")
    library = SongLibrary(tmp_path / "library")
    entry = library.add(source)
    stored = tmp_path / "library" / entry["file"]
    assert library.remove(source) is True
    assert not stored.exists()
    assert library.songs() == []
    assert library.remove(source) is False


def test_add_rejects_missing_source(tmp_path):
    library = SongLibrary(tmp_path / "library")
    with pytest.raises(OSError):
        library.add(tmp_path / "missing.mid")
