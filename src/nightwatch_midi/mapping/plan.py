"""Compile note attacks into game-friendly, absolute wall-clock input events."""
from dataclasses import dataclass
import math

from .profile import Binding, InstrumentProfile
from ..midi.parser import Song


@dataclass(frozen=True)
class Timing:
    lead: float = 0.025
    hold: float = 0.035
    gap: float = 0.025
    tail: float = 0.010


TIMINGS = {
    "standard": Timing(),
    "stable": Timing(0.040, 0.050, 0.040, 0.015),
    "fast": Timing(0.015, 0.025, 0.015, 0.005),
}


@dataclass(frozen=True)
class Action:
    time: float
    kind: str
    value: str


ACTION_ORDER = {"key_up": 0, "mouse_up": 1, "mouse_down": 2, "key_down": 3}


@dataclass(frozen=True)
class Plan:
    actions: tuple[Action, ...]
    duration: float
    selected: int
    mapped: int
    folded: int
    skipped: int
    simplified: int
    played: int = 0
    density_dropped: int = 0
    max_shift: float = 0.0
    compiled_speed: float | None = None
    timing: Timing | None = None
    source_duration: float = 0.0
    trimmed: float = 0.0
    source_cues: tuple[tuple[float, float], ...] = ()


def build_plan(song: Song, profile: InstrumentProfile, *, track: int | None = None,
               channel: int | None = None, transpose: int = 0, fold: bool = True,
               chords: bool = False, exclude_drums: bool = True, note_gap: float | None = None,
               speed: float = 1.0, timing: Timing = TIMINGS["standard"],
               density: str = "rhythm", trim_leading: bool = False,
               onset_window: float = 0.030) -> Plan:
    """Margins are physical seconds. Select attacks before folding pitches.

    A displaced/suppressed note is never resurrected after another note ends.
    'rhythm' caps onset displacement at 60 ms; 'complete' explicitly queues notes.
    Both modes reduce simultaneous chords according to the selected voicing.
    """
    if not math.isfinite(speed) or speed <= 0 or density not in ("score", "rhythm", "complete"):
        raise ValueError("Invalid speed or density strategy")
    if note_gap is not None:
        timing = Timing(timing.lead, timing.hold, note_gap, timing.tail)
    if any(not math.isfinite(v) or v < 0 for v in (timing.lead, timing.hold, timing.gap, timing.tail)):
        raise ValueError("Invalid timing margin")
    if timing.hold <= 0:
        raise ValueError("Minimum hold must be positive")
    if not math.isfinite(onset_window) or not 0 <= onset_window <= 0.1:
        raise ValueError("Invalid onset grouping window")
    pitches = sorted(int(n) for n in profile.midi_notes)
    if not pitches:
        raise ValueError("所选 Profile 没有 MIDI 音高映射")
    selected_notes = [n for n in song.notes if
                      (track is None or n.track == track) and (channel is None or n.channel == channel)
                      and (not exclude_drums or n.channel != 9)]
    selected_notes.sort(key=lambda n: (n.start, n.id))
    clusters = []
    for note in selected_notes:
        if not clusters or note.start - clusters[-1][0].start > onset_window + 1e-9:
            clusters.append([])
        clusters[-1].append(note)
    simplified = skipped = mapped = folded = 0
    groups = []
    for cluster in clusters:
        ranked = sorted(cluster, key=lambda n: (n.pitch, n.velocity, n.id), reverse=True)
        candidates = ranked if chords else ranked[:1]
        simplified += len(ranked) - len(candidates)
        voices = []
        for note in candidates:
            pitch = note.pitch + transpose
            binding = profile.binding(pitch)
            changed = False
            if binding is None and fold:
                choices = [p for p in pitches if (p - pitch) % 12 == 0]
                if choices:
                    pitch = min(choices, key=lambda p: (abs(p - pitch), p))
                    binding, changed = profile.binding(pitch), True
            if binding is None:
                skipped += 1
                continue
            if voices and (set(binding.buttons) != set(voices[0][1].buttons)
                           or binding.key in {b.key for _, b in voices}):
                simplified += 1
                continue
            voices.append((note, binding))
            mapped += 1
            folded += int(changed)
        if voices:
            groups.append((min(n.start for n, _ in voices), voices))
    # Folding never changes melody priority, even if a high note maps below a bass note.
    groups.sort(key=lambda g: g[0])
    trim = groups[0][0] if groups and trim_leading else 0.0
    lead_in = timing.lead if groups else 0.0
    actions = []
    cues = []
    current_buttons: tuple[str, ...] = ()
    last_release: float | None = None
    dropped = played = 0
    max_shift = 0.0
    for index, (start, voices) in enumerate(groups):
        desired = (start - trim) / speed + lead_in
        buttons = tuple(sorted(voices[0][1].buttons))
        changed = buttons != current_buttons
        transition = max(timing.gap, timing.tail + timing.lead if changed else 0)
        earliest = (last_release + transition) if last_release is not None else lead_in
        onset = max(desired, earliest)
        shift = onset - desired
        shift_limit = 0.0 if density == "score" else 0.060
        if density != "complete" and shift > shift_limit + 1e-9:
            dropped += len(voices)
            continue
        max_shift = max(max_shift, shift)
        cues.append((onset, start))
        next_limit = float("inf")
        if index + 1 < len(groups):
            next_start, next_voices = groups[index + 1]
            next_changed = set(next_voices[0][1].buttons) != set(buttons)
            next_margin = max(timing.gap, timing.tail + timing.lead if next_changed else 0)
            next_limit = (next_start - trim) / speed + lead_in - next_margin
        if changed:
            swap = onset - timing.lead
            for button in current_buttons:
                if button not in buttons:
                    actions.append(Action(swap, "mouse_up", button))
            for button in buttons:
                if button not in current_buttons:
                    actions.append(Action(swap, "mouse_down", button))
        ends = []
        for note, binding in voices:
            end = max(onset + timing.hold, min((note.end - trim) / speed + lead_in, next_limit))
            actions.append(Action(onset, "key_down", binding.key))
            actions.append(Action(end, "key_up", binding.key))
            ends.append(end)
            played += 1
        last_release = max(ends)
        current_buttons = buttons
    if last_release is not None:
        for button in current_buttons:
            actions.append(Action(last_release + timing.tail, "mouse_up", button))
    # Stable sort: all key releases before modifiers, modifiers before key presses.
    actions.sort(key=lambda a: (a.time, ACTION_ORDER[a.kind]))
    source_duration = max(0.0, song.duration - trim) / speed
    duration = max(source_duration + lead_in, max((a.time for a in actions), default=0)) if actions else 0.0
    return Plan(tuple(actions), duration, len(selected_notes), mapped, folded, skipped, simplified,
                played, dropped, max_shift, speed, timing, source_duration, trim, tuple(cues))


def slice_plan(plan: Plan, start_at: float) -> Plan:
    """Rebase the timeline to start_at, restoring held mouse buttons at time zero.

    Notes that begin before the cut are dropped whole: their key release is
    removed so we never send a key_up for a key that was never pressed.
    """
    if start_at <= 1e-9 or not plan.actions:
        return plan
    held_buttons: list[str] = []
    pending_keys: set[str] = set()
    kept: list[Action] = []
    for action in plan.actions:
        if action.time < start_at - 1e-9:
            if action.kind == "mouse_down" and action.value not in held_buttons:
                held_buttons.append(action.value)
            elif action.kind == "mouse_up" and action.value in held_buttons:
                held_buttons.remove(action.value)
            elif action.kind == "key_down":
                pending_keys.add(action.value)
            elif action.kind == "key_up":
                pending_keys.discard(action.value)
            continue
        if action.kind == "key_up" and action.value in pending_keys:
            pending_keys.discard(action.value)
            continue
        kept.append(Action(action.time - start_at, action.kind, action.value))
    preamble = [Action(0.0, "mouse_down", button) for button in held_buttons]
    actions = tuple(sorted(preamble + kept, key=lambda a: (a.time, ACTION_ORDER[a.kind])))
    cues = tuple((time - start_at, source) for time, source in plan.source_cues if time >= start_at - 1e-9)
    return Plan(actions, max(0.0, plan.duration - start_at), plan.selected, plan.mapped, plan.folded,
                plan.skipped, plan.simplified, plan.played, plan.density_dropped, plan.max_shift,
                plan.compiled_speed, plan.timing, max(0.0, plan.source_duration - start_at),
                plan.trimmed, cues)
