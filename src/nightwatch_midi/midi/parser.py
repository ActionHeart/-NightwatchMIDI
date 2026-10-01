"""MIDI ticks/tempo to absolute note spans; no instrument or input bindings."""
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path

import mido
from .rhythm import RhythmMap, TempoPoint, MeterPoint


@dataclass(frozen=True)
class Note:
    id: int
    pitch: int
    start: float
    end: float
    track: int
    channel: int
    velocity: int


@dataclass(frozen=True)
class Song:
    notes: tuple[Note, ...]
    duration: float
    track_names: tuple[str, ...]
    warnings: tuple[str, ...] = ()
    rhythm: RhythmMap = RhythmMap()


def read_midi(path: str | Path) -> Song:
    return parse_midi(mido.MidiFile(filename=str(path)))


def decode_track_name(name: str) -> str:
    try:
        raw = name.encode("latin1")
    except UnicodeEncodeError:
        return name
    for encoding in ("utf-8", "gb18030"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            pass
    return name


def parse_midi(mid: mido.MidiFile) -> Song:
    if mid.type not in (0, 1):
        raise ValueError("暂不支持 Type 2 异步 MIDI，请导出为 Type 0 或 Type 1")
    if mid.ticks_per_beat <= 0:
        raise ValueError("暂不支持 SMPTE 时间格式，请导出为 PPQN MIDI")
    events, names = [], []
    for track_id, track in enumerate(mid.tracks):
        tick = 0
        names.append(decode_track_name(track.name) or f"音轨 {track_id + 1}")
        for index, msg in enumerate(track):
            tick += msg.time
            events.append((tick, track_id, index, msg))
    events.sort(key=lambda e: e[:3])
    tempo, last_tick, seconds, next_id = 500000, 0, 0.0, 0
    held = defaultdict(deque)
    sustained = defaultdict(list)
    pedal = defaultdict(bool)
    notes, warnings = [], []
    ignored = set()
    tempos, meters = [TempoPoint()], [MeterPoint()]

    def finish(item, end):
        ident, msg, start, track_id = item
        if end > start:
            notes.append(Note(ident, msg.note, start, end, track_id, msg.channel, msg.velocity))

    for tick, track, _, msg in events:
        seconds += mido.tick2second(tick - last_tick, mid.ticks_per_beat, tempo)
        last_tick = tick
        if msg.type == "set_tempo":
            if msg.tempo <= 0:
                raise ValueError("MIDI 中存在无效速度")
            tempo = msg.tempo
            point = TempoPoint(seconds, tick / mid.ticks_per_beat, tempo, True)
            if tempos[-1].quarter == point.quarter:
                tempos[-1] = point
            else:
                tempos.append(point)
        elif msg.type == "time_signature":
            if msg.numerator <= 0 or msg.denominator <= 0 or msg.notated_32nd_notes_per_beat <= 0:
                raise ValueError("MIDI 中存在无效拍号")
            point = MeterPoint(tick / mid.ticks_per_beat, msg.numerator, msg.denominator,
                               msg.notated_32nd_notes_per_beat, True)
            if meters[-1].quarter == point.quarter:
                meters[-1] = point
            elif (meters[-1].numerator, meters[-1].denominator, meters[-1].notated_32nds) != (
                point.numerator, point.denominator, point.notated_32nds
            ):
                meters.append(point)
        elif msg.type == "note_on" and msg.velocity > 0:
            held[(track, msg.channel, msg.note)].append((next_id, msg, seconds, track))
            next_id += 1
        elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
            queue = held[(track, msg.channel, msg.note)]
            if queue:
                item = queue.popleft()
                if pedal[msg.channel]:
                    sustained[msg.channel].append(item)
                else:
                    finish(item, seconds)
        elif msg.type == "control_change":
            ch = msg.channel
            if msg.control == 64:
                pedal[ch] = msg.value >= 64
                if not pedal[ch]:
                    for item in sustained.pop(ch, []):
                        finish(item, seconds)
            elif msg.control in (120, 123):
                for (_, channel, _), queue in held.items():
                    if channel == ch:
                        while queue:
                            item = queue.popleft()
                            if msg.control == 123 and pedal[ch]:
                                sustained[ch].append(item)
                            else:
                                finish(item, seconds)
                if msg.control == 120:
                    for item in sustained.pop(ch, []):
                        finish(item, seconds)
            elif msg.control == 121:
                pedal[ch] = False
                for item in sustained.pop(ch, []):
                    finish(item, seconds)
            else:
                ignored.add("其他控制器")
        elif msg.type in ("pitchwheel", "aftertouch", "polytouch"):
            ignored.add("弯音/触后")
    unfinished = [item for queue in held.values() for item in queue]
    unfinished += [item for queue in sustained.values() for item in queue]
    for item in unfinished:
        finish(item, seconds)
    if unfinished:
        warnings.append(f"{len(unfinished)} 个未结束音符在文件末尾截断")
    if ignored:
        warnings.append("已忽略：" + "、".join(sorted(ignored)))
    return Song(tuple(sorted(notes, key=lambda n: (n.start, n.id))), seconds, tuple(names), tuple(warnings),
                RhythmMap(tuple(tempos), tuple(meters)))
