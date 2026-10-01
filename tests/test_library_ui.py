from pathlib import Path

from PySide6.QtCore import Qt

from nightwatch_midi.library import SongLibrary
from nightwatch_midi.ui.midi_player import MidiPlayer
from nightwatch_midi.ui.player_view import LibraryItemDelegate


DEMO = Path(__file__).resolve().parents[1] / "tests/fixtures/twinkle_twinkle.mid"
OTHER = Path(__file__).resolve().parents[1] / "tests/fixtures/chromatic_48_85.mid"


def row_data(player, index=0):
    item = player.library_list.item(index)
    return item.data(LibraryItemDelegate.DATA_ROLE)


def test_import_prompts_and_adds_to_library(app):
    player = MidiPlayer()
    player.show()
    app.processEvents()
    assert not player.library_prompt.isVisible()
    player.load_file(DEMO)
    app.processEvents()
    assert player.library_prompt.isVisible()
    player.library_add_button.click()
    app.processEvents()
    assert not player.library_prompt.isVisible()
    assert player.library.contains(DEMO)
    assert player.library_list.count() == 1
    assert player.library_list.item(0).text() == DEMO.name
    player.close()


def test_skip_keeps_library_empty(app):
    player = MidiPlayer()
    player.show()
    app.processEvents()
    player.load_file(DEMO)
    player.library_skip_button.click()
    app.processEvents()
    assert not player.library_prompt.isVisible()
    assert not player.library.contains(DEMO)
    assert player.library_list.count() == 0
    assert not player.library_load_button.isEnabled()
    player.close()


def test_library_selection_loads_song_without_prompt(app):
    SongLibrary().add(DEMO)
    player = MidiPlayer()
    player.show()
    app.processEvents()
    assert player.library_list.count() == 1
    assert not player.library_load_button.isEnabled()
    player.library_list.setCurrentRow(0)
    assert player.library_load_button.isEnabled()
    player.library_load_button.click()
    app.processEvents()
    assert player.song is not None
    assert player.file_label.text() == DEMO.name
    assert not player.library_prompt.isVisible()
    assert player.tabs.currentWidget() is player.play_page
    player.close()


def test_double_click_loads_library_song(app):
    SongLibrary().add(DEMO)
    player = MidiPlayer()
    player.library_list.setCurrentRow(0)
    player.library_list.itemDoubleClicked.emit(player.library_list.item(0))
    app.processEvents()
    assert player.song is not None
    assert player.tabs.currentWidget() is player.play_page
    player.close()


def test_reimport_of_library_song_skips_prompt(app):
    player = MidiPlayer()
    player.show()
    app.processEvents()
    player.load_file(DEMO)
    player.library_add_button.click()
    player.load_file(DEMO)
    app.processEvents()
    assert not player.library_prompt.isVisible()
    player.close()


def test_import_to_library_copies_file(app, monkeypatch):
    player = MidiPlayer()
    monkeypatch.setattr("nightwatch_midi.ui.midi_player.QFileDialog.getOpenFileName",
                        lambda *args, **kwargs: (str(DEMO), ""))
    player.import_to_library()
    assert player.library.contains(DEMO)
    assert player.library_list.count() == 1
    assert player.library_list.currentItem() is not None
    assert player.library_load_button.isEnabled()
    player.close()


def test_library_search_and_favorites_filter(app):
    library = SongLibrary()
    library.add(DEMO)
    other = library.add(OTHER)
    library.update(library.root / other["file"], favorite=True)
    player = MidiPlayer()
    assert player.library_list.count() == 2
    player.library_search.setText("twink")
    assert player.library_list.count() == 1
    player.library_search.clear()
    player.library_favorites_only.setChecked(True)
    assert player.library_list.count() == 1
    assert row_data(player)["favorite"] is True
    player.library_favorites_only.setChecked(False)
    assert player.library_list.count() == 2
    player.close()


def test_library_info_shows_metadata_and_optimization(app):
    library = SongLibrary()
    entry = library.add(DEMO, meta={"duration": 24.0, "notes": 42, "bpm": "120.0"})
    library.set_optimized(library.root / entry["file"],
                          {"transpose": -12, "folded": 2, "density_dropped": 3, "speed": 1.0})
    player = MidiPlayer()
    player.library_list.setCurrentRow(0)
    assert row_data(player)["badge"] == "已优化"
    text = player.library_info.text()
    assert "音符 42" in text and "移调 -12" in text and "跳过 3" in text
    player.close()


def test_toggle_favorite_updates_entry(app):
    SongLibrary().add(DEMO)
    player = MidiPlayer()
    player.library_list.setCurrentRow(0)
    player.toggle_favorite()
    assert player.library.find(DEMO)["favorite"] is True
    assert row_data(player)["favorite"] is True
    player.toggle_favorite()
    assert player.library.find(DEMO)["favorite"] is False
    assert row_data(player)["favorite"] is False
    player.close()


def test_library_rows_carry_metadata(app):
    SongLibrary().add(DEMO, meta={"duration": 24.0, "notes": 42, "bpm": "120.0"})
    player = MidiPlayer()
    data = row_data(player)
    assert data["title"] == DEMO.name
    assert "时长 00:24" in data["meta"] and "42 音符" in data["meta"] and "BPM 120.0" in data["meta"]
    player.close()


def test_library_star_signal_toggles_favorite(app):
    SongLibrary().add(DEMO)
    player = MidiPlayer()
    item = player.library_list.item(0)
    player.library_list.itemDelegate().favorite_toggled.emit(item.data(Qt.ItemDataRole.UserRole))
    assert player.library.find(DEMO)["favorite"] is True
    assert row_data(player)["favorite"] is True
    player.close()


def test_library_empty_state_message(app):
    player = MidiPlayer()
    assert not player.library_empty.isHidden()
    assert "曲库还是空的" in player.library_empty.text()
    player.library_search.setText("zzz")
    assert "没有符合条件" in player.library_empty.text()
    player.library_search.clear()
    assert "曲库还是空的" in player.library_empty.text()
    player.close()


def test_open_library_folder_uses_library_root(app, monkeypatch):
    opened = []
    monkeypatch.setattr("nightwatch_midi.ui.midi_player.QDesktopServices.openUrl",
                        lambda url: opened.append(url.toLocalFile()))
    player = MidiPlayer()
    player.open_library_folder()
    assert opened and Path(opened[0]).name == "library"
    player.close()


def test_recent_sort_uses_last_played(app):
    library = SongLibrary()
    first = library.add(DEMO)
    library.add(OTHER)
    library.mark_played(library.root / first["file"])
    player = MidiPlayer()
    player.library_sort.setCurrentIndex(player.library_sort.findData("recent"))
    assert DEMO.name in player.library_list.item(0).text()
    player.close()


def test_library_load_records_play_count(app):
    library = SongLibrary()
    entry = library.add(DEMO, meta={"duration": 24.0, "notes": 42, "bpm": "120.0"})
    player = MidiPlayer()
    player.library_list.setCurrentRow(0)
    player.library_load_button.click()
    app.processEvents()
    loaded = SongLibrary().find(DEMO)
    assert loaded["play_count"] == 1 and loaded["last_played"]
    player.close()


def test_remove_from_library(app):
    SongLibrary().add(DEMO)
    player = MidiPlayer()
    player.library_list.setCurrentRow(0)
    player.remove_from_library()
    assert not player.library.contains(DEMO)
    assert player.library_list.count() == 0
    assert not player.library_load_button.isEnabled()
    player.close()
