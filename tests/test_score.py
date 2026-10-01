import pytest

from nightwatch_midi.mapping.profile import load_profile
from nightwatch_midi.score import (KEY_EXAMPLE, NUMBERED_EXAMPLE, build_midi,
                                   build_song, parse_directives, parse_keys,
                                   parse_numbered)


def test_numbered_basic_scale_and_duration():
    score = parse_numbered("1 2 3 4 5 6 7")
    assert [note.pitch for note in score.notes] == [60, 62, 64, 65, 67, 69, 71]
    assert all(note.duration == 1.0 for note in score.notes)
    assert score.duration == 7.0


def test_numbered_duration_suffixes():
    score = parse_numbered("1- 2/ 3// 4. 5")
    assert [note.duration for note in score.notes] == [2.0, 0.5, 0.25, 1.5, 1.0]
    assert [note.start for note in score.notes] == [0.0, 2.0, 2.5, 2.75, 4.25]


def test_numbered_rest_and_standalone_dash():
    score = parse_numbered("1 - 0 2")
    assert [note.pitch for note in score.notes] == [60, 62]
    assert score.notes[0].duration == 2.0
    assert score.notes[1].start == 3.0


def test_numbered_octave_accidental_and_key():
    assert [n.pitch for n in parse_numbered("1, 1 1'").notes] == [48, 60, 72]
    assert [n.pitch for n in parse_numbered("#4 b7").notes] == [66, 70]
    assert [n.pitch for n in parse_numbered("1 2 3", key="G").notes] == [67, 69, 71]
    assert [n.pitch for n in parse_numbered("1", key="Bb").notes] == [70]


def test_numbered_chord_and_directives():
    score = parse_numbered("BPM 90\n1=C 4/4\n[1 3 5]- 2")
    assert [note.pitch for note in score.notes[:3]] == [60, 64, 67]
    assert score.notes[0].start == score.notes[1].start == score.notes[2].start == 0.0
    assert score.notes[0].duration == 2.0
    assert score.notes[3].pitch == 62 and score.notes[3].start == 2.0
    assert parse_directives("BPM 90\n1=G 3/4") == {"bpm": 90, "key": "G", "meter": (3, 4)}


def test_numbered_errors():
    with pytest.raises(ValueError, match="没有解析到"):
        parse_numbered("")
    with pytest.raises(ValueError, match="无法识别"):
        parse_numbered("8")
    with pytest.raises(ValueError, match="和弦"):
        parse_numbered("[1 3")


def test_key_notation_plain_scale_and_chords():
    profile = load_profile(name="delta_harmonica.json")
    score = parse_keys("Z X C V B N M", profile)
    assert [note.pitch for note in score.notes] == [60, 62, 64, 65, 67, 69, 71]
    assert not score.warnings
    chord = parse_keys("Z+C", profile)
    assert [note.pitch for note in chord.notes] == [60, 64]
    explicit = parse_keys("[72] Z", profile)
    assert [note.pitch for note in explicit.notes] == [72, 60]


def test_key_notation_durations_rest_and_unknown_key():
    profile = load_profile(name="delta_harmonica.json")
    score = parse_keys("Z- X/ 0 M", profile)
    assert [note.duration for note in score.notes] == [2.0, 0.5, 1.0]
    assert score.notes[-1].start == 3.5
    with pytest.raises(ValueError, match="没有按键"):
        parse_keys("Q", profile)
    with pytest.raises(ValueError, match="没有解析到"):
        parse_keys("", profile)


def test_build_midi_and_song_roundtrip():
    score = parse_numbered(NUMBERED_EXAMPLE)
    mid = build_midi(score)
    assert mid.type == 1
    song = build_song(score)
    assert len(song.notes) == len(score.notes)
    assert song.duration == pytest.approx(score.duration * 60 / score.bpm)
    assert song.rhythm.tempos and 60000000 / song.rhythm.tempos[0].microseconds == pytest.approx(120)
    key_score = parse_keys(KEY_EXAMPLE, load_profile(name="delta_harmonica.json"))
    assert len(build_song(key_score).notes) == len(key_score.notes)
