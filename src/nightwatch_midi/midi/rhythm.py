"""Tempo and meter maps. Meter never multiplies MIDI tick-to-second timing."""
from bisect import bisect_right
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class TempoPoint:
    seconds: float = 0.0
    quarter: float = 0.0
    microseconds: int = 500000
    explicit: bool = False


@dataclass(frozen=True)
class MeterPoint:
    quarter: float = 0.0
    numerator: int = 4
    denominator: int = 4
    notated_32nds: int = 8
    explicit: bool = False

    @property
    def beat_quarters(self) -> float:
        return 32 / self.denominator / self.notated_32nds


@dataclass(frozen=True)
class BeatPosition:
    bar: int
    beat: float
    numerator: int
    denominator: int
    quarter_bpm: float


@dataclass(frozen=True)
class RhythmMap:
    tempos: tuple[TempoPoint, ...] = (TempoPoint(),)
    meters: tuple[MeterPoint, ...] = (MeterPoint(),)

    def at(self, seconds: float) -> BeatPosition:
        seconds = max(0.0, seconds)
        index = max(0, bisect_right([p.seconds for p in self.tempos], seconds + 1e-9) - 1)
        tempo = self.tempos[index]
        quarter = tempo.quarter + (seconds - tempo.seconds) * 1000000 / tempo.microseconds
        meter_index = max(0, bisect_right([p.quarter for p in self.meters], quarter + 1e-8) - 1)
        bar = 1
        for previous, following in zip(self.meters[:meter_index], self.meters[1:meter_index + 1]):
            measures = (following.quarter - previous.quarter) / (previous.numerator * previous.beat_quarters)
            # A mid-bar signature change starts a new bar in our display convention.
            bar += max(0, math.ceil(measures - 1e-8))
        meter = self.meters[meter_index]
        beats = max(0.0, (quarter - meter.quarter) / meter.beat_quarters)
        completed = math.floor((beats + 1e-8) / meter.numerator)
        beat = max(0.0, beats - completed * meter.numerator) + 1
        return BeatPosition(bar + completed, beat, meter.numerator, meter.denominator,
                            60000000 / tempo.microseconds)

    def describe(self, speed: float = 1.0) -> str:
        bpms = [60000000 / point.microseconds for point in self.tempos]
        bpm_text = f"{min(bpms):.2f}" if max(bpms) - min(bpms) < 0.001 else f"{min(bpms):.2f}–{max(bpms):.2f}"
        meter = self.meters[0]
        tempo_changes = sum(a.microseconds != b.microseconds for a, b in zip(self.tempos, self.tempos[1:]))
        meter_changes = sum((a.numerator, a.denominator, a.notated_32nds) != (b.numerator, b.denominator, b.notated_32nds)
                            for a, b in zip(self.meters, self.meters[1:]))
        assumed = []
        if not self.tempos[0].explicit:
            assumed.append("开头未标速度，按 120 BPM")
        if not self.meters[0].explicit:
            assumed.append("开头未标拍号，按 4/4 显示")
        text = (f"原谱四分音符 BPM {bpm_text} | 开头拍号 {meter.numerator}/{meter.denominator} | "
                f"速度变化 {tempo_changes} 次 / 拍号变化 {meter_changes} 次\n"
                f"播放倍速 {speed:.2f}×；BPM 随倍速同比变化，拍号不改变播放速度。")
        return text + (("\n" + "；".join(assumed)) if assumed else "")
