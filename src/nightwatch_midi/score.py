"""Text score import: keyboard-key scores and numbered notation to MIDI.

Both parsers accept a compact plain-text syntax:

Numbered notation (简谱)
    1=C 4/4 / BPM 120       optional directives on their own line
    1 2 3 4 5 6 7 0         scale degrees, 0 is a rest
    #4 / b7                 accidentals
    5' / 5,                 octave up / down (repeatable)
    1- 1-- 1/ 1// 1.        duration: dashes add beats, slash halves, dot x1.5
    [1 3 5]-                chord with the duration suffix after the bracket
    -                       standalone dash extends the previous note by one beat
    | and newlines          ignored

Keyboard-key scores (按键谱)
    Z X C V B N M           key names resolved through the loaded instrument profile
    [60]                    explicit MIDI pitch
    Z+X                     keys struck together (chord)
    same duration suffixes as numbered notation
"""
from dataclasses import dataclass, replace
import re

import mido

from .mapping.profile import InstrumentProfile
from .midi.parser import parse_midi

SCALE = (0, 2, 4, 5, 7, 9, 11)
KEY_BASE = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
SUFFIX_CHARS = "-./"
DIRECTIVE_BPM = re.compile(r"(?i)^bpm\s*[:=]?\s*(\d{1,3})$")
DIRECTIVE_KEY = re.compile(r"^1\s*=\s*([#b]?[A-Ga-g])$")
DIRECTIVE_METER = re.compile(r"^(\d{1,2})\s*/\s*(\d{1,2})$")
EXPLICIT_PITCH = re.compile(r"^\[\s*(\d{1,3})\s*\]$")


@dataclass(frozen=True)
class ScoreNote:
    pitch: int
    start: float
    duration: float


@dataclass(frozen=True)
class Score:
    notes: tuple[ScoreNote, ...]
    bpm: int = 120
    numerator: int = 4
    denominator: int = 4
    warnings: tuple[str, ...] = ()
    title: str = "谱曲作品"

    @property
    def duration(self) -> float:
        return max((note.start + note.duration for note in self.notes), default=0.0)


def key_name_offset(name: str) -> int:
    name = name.strip()
    if not name or name[0].upper() not in KEY_BASE:
        raise ValueError(f"无法识别的调号：{name or '空'}")
    offset = KEY_BASE[name[0].upper()]
    tail = name[1:2]
    if tail == "#":
        offset += 1
    elif tail.lower() == "b":
        offset -= 1
    return offset


def read_suffix(token: str) -> tuple[str, float]:
    """Split a duration suffix (-, ., /) off a token and return its beat count."""
    core, dashes, slashes, dot = token, 0, 0, False
    while core and core[-1] in SUFFIX_CHARS:
        char = core[-1]
        if char == "-":
            dashes += 1
        elif char == "/":
            slashes += 1
        else:
            dot = True
        core = core[:-1]
    beats = (1 + dashes) * (1.5 if dot else 1.0) / (2 ** slashes)
    return core, beats


def _octave_marks(token: str) -> tuple[str, int]:
    marks = 0
    while token and token[-1] in ("'", ","):
        marks += 1 if token[-1] == "'" else -1
        token = token[:-1]
    return token, marks


def _numbered_pitch(token: str, key_offset: int, octave: int, line: int) -> int:
    accidental = 0
    if token[:1] in ("#", "b"):
        accidental = 1 if token[0] == "#" else -1
        token = token[1:]
    if len(token) != 1 or not token.isdigit() or not 1 <= int(token) <= 7:
        raise ValueError(f"第 {line} 行：无法识别的音符「{token}」")
    degree = int(token)
    return 60 + key_offset + SCALE[degree - 1] + 12 * octave + accidental


def parse_numbered(text: str, *, key: str = "C", bpm: int = 120,
                   numerator: int = 4, denominator: int = 4, octave: int = 0) -> Score:
    key_offset = key_name_offset(key) if key else 0
    notes: list[ScoreNote] = []
    warnings: list[str] = []
    beat = 0.0
    for line_number, raw_line in enumerate(text.splitlines(), 1):
        line = raw_line.replace("|", " ").replace("｜", " ").replace("[", " [ ").replace("]", " ] ")
        tokens = line.split()
        if not tokens:
            continue
        if _consume_directives(tokens):
            continue
        index = 0
        while index < len(tokens):
            token = tokens[index]
            index += 1
            if token == "-":
                if notes:
                    notes[-1] = replace(notes[-1], duration=notes[-1].duration + 1.0)
                    beat += 1.0
                continue
            if token == "[":
                group = []
                while index < len(tokens) and tokens[index] != "]":
                    group.append(tokens[index])
                    index += 1
                if index >= len(tokens) or not group:
                    raise ValueError(f"第 {line_number} 行：和弦缺少 ] 或内容")
                index += 1
                outer = 1.0
                if index < len(tokens) and tokens[index] and all(c in SUFFIX_CHARS for c in tokens[index]):
                    outer = read_suffix("x" + tokens[index])[1]
                    index += 1
                pitches = []
                for part in group:
                    core, marks = _octave_marks(part)
                    pitches.append(_numbered_pitch(core, key_offset, octave + marks, line_number))
                for pitch in pitches:
                    notes.append(ScoreNote(pitch, beat, outer))
                beat += outer
                continue
            core, beats = read_suffix(token)
            core, marks = _octave_marks(core)
            if core == "0":
                beat += beats
                continue
            pitch = _numbered_pitch(core, key_offset, octave + marks, line_number)
            notes.append(ScoreNote(pitch, beat, beats))
            beat += beats
    if not notes:
        raise ValueError("没有解析到任何音符，请检查谱面文本")
    return Score(tuple(notes), bpm, numerator, denominator, tuple(warnings))


def key_pitch_map(profile: InstrumentProfile) -> dict[str, int]:
    """Resolve key names to the plain (no-mouse) or nearest binding's pitch."""
    best: dict[str, tuple[tuple[int, int, int], int]] = {}
    for pitch_text, _ in profile.midi_notes.items():
        pitch = int(pitch_text)
        binding = profile.binding(pitch)
        if binding is None:
            continue
        rank = (len(binding.buttons), abs(pitch - 60), pitch)
        name = binding.key.casefold()
        if name not in best or rank < best[name][0]:
            best[name] = (rank, pitch)
    return {name: pitch for name, (_, pitch) in best.items()}


def parse_keys(text: str, profile: InstrumentProfile, *, bpm: int = 120,
               numerator: int = 4, denominator: int = 4) -> Score:
    pitches_by_key = key_pitch_map(profile)
    if not pitches_by_key:
        raise ValueError("当前乐器配置没有可用的按键映射")
    notes: list[ScoreNote] = []
    warnings: list[str] = []
    beat = 0.0
    for line_number, raw_line in enumerate(text.splitlines(), 1):
        line = raw_line.replace("|", " ").replace("｜", " ")
        tokens = line.split()
        if not tokens:
            continue
        if _consume_directives(tokens):
            continue
        for token in tokens:
            if token == "-":
                if notes:
                    notes[-1] = replace(notes[-1], duration=notes[-1].duration + 1.0)
                    beat += 1.0
                continue
            core, beats = read_suffix(token)
            if core in ("0", ""):
                beat += beats
                continue
            pitches = []
            for part in core.split("+"):
                explicit = EXPLICIT_PITCH.match(part)
                if explicit:
                    pitch = int(explicit.group(1))
                    if not 0 <= pitch <= 127:
                        raise ValueError(f"第 {line_number} 行：MIDI 音高超出 0–127")
                    pitches.append(pitch)
                    continue
                pitch = pitches_by_key.get(part.casefold())
                if pitch is None:
                    raise ValueError(f"第 {line_number} 行：当前乐器没有按键「{part}」")
                binding = profile.binding(pitch)
                if binding and binding.buttons:
                    warnings.append(f"按键「{part}」没有无鼠标组合的映射，已按音高 {pitch} 处理")
                pitches.append(pitch)
            for pitch in pitches:
                notes.append(ScoreNote(pitch, beat, beats))
            beat += beats
    if not notes:
        raise ValueError("没有解析到任何音符，请检查谱面文本")
    return Score(tuple(notes), bpm, numerator, denominator, tuple(dict.fromkeys(warnings)))


def _consume_directives(tokens: list[str]) -> bool:
    """True when the whole line is made of directives (BPM 120 / 1=C / 4/4)."""
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if re.fullmatch(r"(?i)bpm\s*[:=]?\s*\d{1,3}", token):
            index += 1
            continue
        if (re.fullmatch(r"(?i)bpm\s*[:=]?", token) and index + 1 < len(tokens)
                and tokens[index + 1].isdigit()):
            index += 2
            continue
        if DIRECTIVE_KEY.fullmatch(token) or DIRECTIVE_METER.fullmatch(token):
            index += 1
            continue
        return False
    return True


def parse_directives(text: str) -> dict:
    found = {}
    for raw_line in text.splitlines():
        tokens = raw_line.replace("|", " ").split()
        index = 0
        while index < len(tokens):
            token = tokens[index]
            match = re.fullmatch(r"(?i)bpm\s*[:=]?\s*(\d{1,3})", token)
            if match:
                found["bpm"] = max(20, min(300, int(match.group(1))))
                index += 1
                continue
            if (re.fullmatch(r"(?i)bpm\s*[:=]?", token) and index + 1 < len(tokens)
                    and tokens[index + 1].isdigit()):
                found["bpm"] = max(20, min(300, int(tokens[index + 1])))
                index += 2
                continue
            match = DIRECTIVE_KEY.fullmatch(token)
            if match:
                found["key"] = match.group(1)
                index += 1
                continue
            match = DIRECTIVE_METER.fullmatch(token)
            if match:
                found["meter"] = (int(match.group(1)), int(match.group(2)))
                index += 1
                continue
            break
    return found


def safe_track_name(name: str, fallback: str = "NightwatchMIDI score") -> str:
    """MIDI text meta is latin-1; keep an ASCII fallback for Chinese titles."""
    try:
        name.encode("latin-1")
        return name
    except UnicodeEncodeError:
        return fallback


def build_midi(score: Score, *, track_name: str = "NightwatchMIDI score", ticks_per_beat: int = 480) -> mido.MidiFile:
    mid = mido.MidiFile(type=1, ticks_per_beat=ticks_per_beat)
    track = mido.MidiTrack()
    track.name = track_name
    track.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(score.bpm), time=0))
    track.append(mido.MetaMessage("time_signature", numerator=score.numerator,
                                  denominator=score.denominator, time=0))
    events = []
    for index, note in enumerate(score.notes):
        start = round(note.start * ticks_per_beat)
        end = max(start + 1, round((note.start + note.duration) * ticks_per_beat))
        events.append((start, 1, index, note.pitch, True))
        events.append((end, 0, index, note.pitch, False))
    events.sort(key=lambda item: item[:3])
    last_tick = 0
    for tick, _, _, pitch, is_on in events:
        if is_on:
            message = mido.Message("note_on", note=pitch, velocity=80, time=tick - last_tick)
        else:
            message = mido.Message("note_off", note=pitch, velocity=0, time=tick - last_tick)
        track.append(message)
        last_tick = tick
    track.append(mido.MetaMessage("end_of_track", time=0))
    mid.tracks.append(track)
    return mid


def build_song(score: Score):
    return parse_midi(build_midi(score))


NUMBERED_EXAMPLE = """\
1=C 4/4
BPM 120
| 1 1 5 5 | 6 6 5- | 4 4 3 3 | 2 2 1- |
| 5 5 4 4 | 3 3 2- | 5 5 4 4 | 3 3 2- |
"""

KEY_EXAMPLE = """\
BPM 120
Z X C V B N M
Z X C V B N M
V V B B N N M -
V V B B N N M -
"""
