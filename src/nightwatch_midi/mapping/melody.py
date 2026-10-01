"""Explainable track/channel suggestions; bindings and range come from a profile."""
from collections import defaultdict
from dataclasses import dataclass
from statistics import median
import math

from .profile import InstrumentProfile
from ..midi.parser import Song


@dataclass(frozen=True)
class MelodyCandidate:
    track: int
    channel: int
    count: int
    score: float
    reason: str


def rank_melodies(song: Song, profile: InstrumentProfile) -> tuple[MelodyCandidate, ...]:
    streams = defaultdict(list)
    for note in song.notes:
        if note.channel != 9:
            streams[(note.track, note.channel)].append(note)
    candidates = []
    for (track, channel), notes in streams.items():
        starts = sorted(set(round(n.start, 2) for n in notes))
        single = len(starts) / len(notes)
        in_range = sum(profile.binding(n.pitch) is not None for n in notes) / len(notes)
        span = max(n.end for n in notes) - min(n.start for n in notes)
        coverage = min(1.0, span / max(song.duration, 0.01))
        # Rank rather than assert: an accompaniment can also be high and monophonic.
        score = 2 * single + 2 * in_range + 2 * coverage + math.log1p(len(notes)) / 4
        score += median(n.pitch for n in notes) / 48
        name = song.track_names[track].casefold()
        if any(word in name for word in ("melody", "vocal", "lead", "旋律", "人声", "主唱")):
            score += 3
        if any(word in name for word in ("bass", "drum", "伴奏", "贝斯", "打击")):
            score -= 3
        reason = f"{len(notes)} 音符；音域内 {in_range:.0%}；起音独立度 {single:.0%}"
        candidates.append(MelodyCandidate(track, channel, len(notes), score, reason))
    return tuple(sorted(candidates, key=lambda c: (-c.score, c.track, c.channel)))
