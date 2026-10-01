from pathlib import Path

import pytest

from nightwatch_midi.ui.midi_player import MidiPlayer


DEMO = Path(__file__).resolve().parents[1] / "tests/fixtures/twinkle_twinkle.mid"


def test_preset_applies_and_manual_change_clears(app):
    player = MidiPlayer()
    assert player.preset_buttons["balance"].isChecked()
    player.load_file(DEMO)
    assert player.preset_buttons["balance"].isChecked()
    player.apply_preset("stable")
    assert player.timing_preset.currentData() == "stable"
    assert player.onset_window.value() == 20
    assert player.preset_buttons["stable"].isChecked()
    player.speed.setValue(1.25)
    assert not any(button.isChecked() for button in player.preset_buttons.values())
    player.apply_preset("fidelity")
    assert player.range_mode.currentData() == "original"
    assert player.transpose.value() == 0 and not player.fold.isChecked()
    assert player.speed.value() == pytest.approx(1.0)
    assert player.preset_buttons["fidelity"].isChecked()
    player.apply_preset("fast")
    assert player.speed.value() == pytest.approx(1.5)
    assert player.timing_preset.currentData() == "fast"
    assert player.preset_buttons["fast"].isChecked()
    player.close()


def test_analysis_summary_mentions_arrangement(app):
    player = MidiPlayer()
    player.load_file(DEMO)
    text = player.analysis_label.text()
    assert "推荐移调" in text and "当前编排" in text and "超音域" in text
    player.close()
