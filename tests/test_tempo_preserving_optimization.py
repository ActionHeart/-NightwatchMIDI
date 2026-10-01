from pathlib import Path

import pytest

from nightwatch_midi.input.backend import MockInputBackend
from nightwatch_midi.midi.parser import Note, Song
from nightwatch_midi.ui.midi_player import MidiPlayer


@pytest.mark.parametrize("speed", [0.75, 1, 1.5])
def test_optimization_preserves_selected_speed_and_absolute_onsets(app, speed):
    player = MidiPlayer()
    player.song = Song(tuple(
        note for i in range(12) for note in (
            Note(i * 2, 48, i * .5, i * .5 + .3, 0, 0, 80),
            Note(i * 2 + 1, 72, i * .5 + .015, i * .5 + .3, 0, 0, 90),
        )), 6, ("Piano",))
    player.track.addItem("Piano", 0)
    player.speed.setValue(speed)
    player.rebuild()
    before = player.plan.density_dropped
    player.optimize()
    assert player.speed.value() == speed
    assert player.plan.density_dropped < before
    assert player.plan.max_shift == 0
    assert player.onset_window.value() == 20
    assert player.plan.played == 12
    for scheduled, source in player.plan.source_cues:
        assert scheduled == pytest.approx((source - player.plan.trimmed) / speed + player.plan.timing.lead)
    assert isinstance(player.backend, MockInputBackend)
    player.close()


def test_clean_melody_does_not_gain_grouping_or_pitch_changes(app):
    player = MidiPlayer()
    path = Path(__file__).resolve().parents[1] / "tests/fixtures/twinkle_twinkle.mid"
    player.load_file(path)
    before = player.plan.actions
    player.optimize()
    assert player.onset_window.value() == 0
    assert player.plan.actions == before
    player.close()
