from pathlib import Path

import mido
import pytest

from nightwatch_midi.midi.parser import parse_midi, read_midi
from nightwatch_midi.mapping.profile import load_profile
from nightwatch_midi.mapping.plan import build_plan, TIMINGS
from nightwatch_midi.ui.midi_player import MidiPlayer


def make_midi(messages):
    mid = mido.MidiFile(type=0, ticks_per_beat=480)
    mid.tracks.append(mido.MidiTrack(messages))
    return mid


def test_meter_changes_bar_count_without_changing_seconds():
    song = parse_midi(make_midi([
        mido.MetaMessage("set_tempo", tempo=500000),
        mido.MetaMessage("time_signature", numerator=4, denominator=4),
        mido.Message("note_on", note=60),
        mido.MetaMessage("time_signature", numerator=2, denominator=4, time=1920),
        mido.MetaMessage("time_signature", numerator=4, denominator=4, time=960),
        mido.Message("note_off", note=60, time=480),
    ]))
    assert song.notes[0].end == pytest.approx(3.5)
    assert (song.rhythm.at(2).bar, song.rhythm.at(2).beat) == (2, 1)
    assert (song.rhythm.at(3).bar, song.rhythm.at(3).beat) == (3, 1)
    assert song.rhythm.at(2.5).numerator == 2
    assert "拍号变化 2 次" in song.rhythm.describe()


def test_six_eight_uses_eighth_note_positions_not_wrong_playback_speed():
    song = parse_midi(make_midi([
        mido.MetaMessage("time_signature", numerator=6, denominator=8),
        mido.Message("note_on", note=60),
        mido.Message("note_off", note=60, time=1440),
    ]))
    assert song.duration == pytest.approx(1.5)
    assert song.rhythm.at(0.25).beat == pytest.approx(2)
    assert song.rhythm.at(1.5).bar == 2
    assert song.rhythm.at(1.5).quarter_bpm == 120


def test_tempo_defaults_before_later_change_and_crossing_long_note():
    song = parse_midi(make_midi([
        mido.Message("note_on", note=60),
        mido.MetaMessage("set_tempo", tempo=1000000, time=480),
        mido.Message("note_off", note=60, time=480),
    ]))
    assert song.duration == pytest.approx(1.5)
    assert song.rhythm.at(0.25).quarter_bpm == 120
    assert song.rhythm.at(0.5).quarter_bpm == 60
    assert song.rhythm.at(1.5).beat == pytest.approx(3)
    assert "开头未标速度" in song.rhythm.describe()


def test_repeated_identical_meter_does_not_start_a_new_measure():
    song = parse_midi(make_midi([
        mido.MetaMessage("time_signature", numerator=4, denominator=4),
        mido.MetaMessage("time_signature", numerator=4, denominator=4, time=480),
    ]))
    assert len(song.rhythm.meters) == 1
    assert (song.rhythm.at(1).bar, song.rhythm.at(1).beat) == (1, 3)


def test_meter_change_and_tempo_change_at_same_tick():
    song = parse_midi(make_midi([
        mido.MetaMessage("time_signature", numerator=3, denominator=4),
        mido.MetaMessage("set_tempo", tempo=1000000, time=1440),
        mido.MetaMessage("time_signature", numerator=6, denominator=8),
    ]))
    pos = song.rhythm.at(2.0)
    assert (pos.bar, pos.beat, pos.numerator, pos.denominator, pos.quarter_bpm) == (2, 2, 6, 8, 60)


@pytest.mark.parametrize("path", sorted((Path(__file__).resolve().parents[1] / "examples").glob("*.mid")), ids=lambda p: p.stem)
def test_original_tempo_matches_mido_and_score_onsets_remain_exact(path):
    song = read_midi(path)
    independent_length = sum(msg.time for msg in mido.MidiFile(path))
    assert song.duration == pytest.approx(independent_length, abs=1e-6)
    plan = build_plan(song, load_profile(name="delta_harmonica.json"), timing=TIMINGS["stable"],
                      density="score", onset_window=0, speed=1.25)
    assert plan.max_shift < 1e-8
    assert plan.source_cues
    for planned_time, original_time in plan.source_cues:
        assert planned_time == pytest.approx(original_time / 1.25 + plan.timing.lead)
    assert plan.duration >= song.duration / 1.25


def test_restore_original_controls_and_bpm_display(app):
    player = MidiPlayer()
    player.song = parse_midi(make_midi([
        mido.MetaMessage("set_tempo", tempo=1000000),
        mido.MetaMessage("time_signature", numerator=3, denominator=4),
        mido.Message("note_on", note=60),
        mido.Message("note_off", note=60, time=480),
    ]))
    player.speed.setValue(0.6)
    player.onset_window.setValue(30)
    player.density.setCurrentIndex(player.density.findData("complete"))
    player.restore_original()
    assert player.speed.value() == 1 and player.onset_window.value() == 0
    assert player.density.currentData() == "score" and not player.trim.isChecked()
    assert "BPM 60.00" in player.rhythm_info.text()
    assert "3/4" in player.rhythm_info.text()
    player.update_beat(player.plan.timing.lead + 0.5)
    assert "第 1.50 拍" in player.beat_label.text()
    assert not player.enable.isChecked()
    player.close()
