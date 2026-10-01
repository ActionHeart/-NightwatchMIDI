from nightwatch_midi.library import SongLibrary
from nightwatch_midi.ui.midi_player import MidiPlayer


def test_load_example_preview_and_play(app):
    player = MidiPlayer()
    player.score_format.setCurrentIndex(player.score_format.findData("numbered"))
    player.load_score_example()
    assert "1 1 5 5" in player.score_editor.toPlainText()
    player.preview_score()
    assert "解析成功" in player.score_result.text()
    player.play_score()
    app.processEvents()
    assert player.song is not None
    assert player.tabs.currentWidget() is player.play_page
    assert player.file_label.text() == "谱曲作品.mid"
    assert "已生成" in player.status.text()
    player.close()


def test_key_format_example_and_invalid_input(app):
    player = MidiPlayer()
    player.load_score_example()
    player.preview_score()
    assert "解析成功" in player.score_result.text()
    player.score_editor.setPlainText("Q")
    player.preview_score()
    assert "解析失败" in player.score_result.text()
    assert "没有按键" in player.score_result.text()
    player.close()


def test_composed_song_saves_to_library(app):
    player = MidiPlayer()
    player.score_format.setCurrentIndex(player.score_format.findData("numbered"))
    player.load_score_example()
    player.score_title.setText("小星星练习")
    player.save_score_to_library()
    assert player.library_list.count() == 1
    entry = SongLibrary().find(player.library.root / "小星星练习.mid")
    assert entry is not None and entry["meta"]["notes"] > 0
    player.close()


def test_numbered_directives_override_controls(app):
    player = MidiPlayer()
    player.score_format.setCurrentIndex(player.score_format.findData("numbered"))
    player.score_editor.setPlainText("BPM 90\n1=G 3/4\n1 2 3")
    player.preview_score()
    assert "90 BPM" in player.score_result.text()
    assert "3/4" in player.score_result.text()
    player.close()


def test_empty_score_reports_failure(app):
    player = MidiPlayer()
    player.preview_score()
    assert "解析失败" in player.score_result.text()
    assert player.song is None
    player.close()
