"""Cancellable manual input test, independent of the future playback engine."""
import math
import time
from collections.abc import Callable, Sequence

from .backend import InputBackend


class InputSession:
    def __init__(self, backend: InputBackend, clock: Callable[[], float] = time.perf_counter,
                 before_press: Callable[[], None] | None = None):
        self.backend = backend
        self.clock = clock
        self.before_press = before_press
        self.deadline: float | None = None
        self.pending: tuple[tuple[str, ...], tuple[str, ...], float] | None = None

    def start(self, keys: Sequence[str], buttons: Sequence[str], duration: float, delay: float = 0) -> None:
        if not math.isfinite(duration) or duration <= 0 or not math.isfinite(delay) or delay < 0:
            raise ValueError("Duration must be positive; delay must be nonnegative")
        self.stop()
        self.pending = (tuple(dict.fromkeys(keys)), tuple(dict.fromkeys(buttons)), duration)
        self.deadline = self.clock() + delay
        self.tick()

    def tick(self) -> None:
        if self.deadline is None or self.clock() < self.deadline:
            return
        if self.pending is None:
            self.stop()
            return
        keys, buttons, duration = self.pending
        self.pending = None
        try:
            if self.before_press is not None:
                self.before_press()
            for key in keys:
                self.backend.key_down(key)
            for button in buttons:
                self.backend.mouse_down(button)
            self.deadline = self.clock() + duration
        except BaseException:
            self.stop()
            raise

    def stop(self) -> None:
        self.deadline = None
        self.pending = None
        self.backend.release_all()
