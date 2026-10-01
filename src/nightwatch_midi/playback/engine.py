"""Single-owner worker with absolute perf_counter deadlines and cancellation."""
import math
import threading
import time
from collections.abc import Callable

from ..input.backend import InputBackend
from ..mapping.plan import Plan


class PlaybackEngine:
    def __init__(self, backend: InputBackend, *, clock: Callable[[], float] = time.perf_counter,
                 wait: Callable[[float], bool] | None = None,
                 before_play: Callable[[], None] | None = None,
                 guard: Callable[[], bool] | None = None):
        self.backend = backend
        self.clock = clock
        self.cancel = threading.Event()
        self.done = threading.Event()
        self._wait = wait or self.cancel.wait
        self.before_play = before_play
        self.guard = guard
        self.thread: threading.Thread | None = None
        self.state = "ready"
        self.error: BaseException | None = None
        self.release_failed = False
        self.origin = 0.0
        self.speed = 1.0
        self.duration = 0.0
        self.base = 0.0
        self.max_lateness = 0.0

    @property
    def position(self) -> float:
        if self.state in ("ready", "countdown"):
            return self.base
        return min(self.duration, self.base + max(0.0, (self.clock() - self.origin) * self.speed))

    def start(self, plan: Plan, *, speed: float = 1.0, delay: float = 5.0, start_at: float = 0.0) -> None:
        if self.thread and self.thread.is_alive():
            raise RuntimeError("Playback is already running")
        if self.release_failed:
            raise RuntimeError("Retry release_all before starting another playback")
        self.cancel.clear()
        self.done.clear()
        self.error = None
        self.thread = threading.Thread(target=self.run, args=(plan,),
                                       kwargs={"speed": speed, "delay": delay, "start_at": start_at},
                                       name="NightwatchMIDI-playback", daemon=False)
        self.thread.start()

    def _until(self, deadline: float) -> bool:
        while not self.cancel.is_set():
            if self.state == "playing" and self.guard and not self.guard():
                raise RuntimeError("目标窗口已切换，已停止播放")
            remaining = deadline - self.clock()
            if remaining <= 1e-9:
                return True
            # Event.wait is interruptible. Each wake recomputes from the same origin.
            if self._wait(min(remaining, 0.02)):
                return False
        return False

    def run(self, plan: Plan, *, speed: float = 1.0, delay: float = 5.0, start_at: float = 0.0) -> None:
        """Blocking entry point also used by deterministic Mock tests."""
        try:
            if not math.isfinite(speed) or speed <= 0 or not math.isfinite(delay) or delay < 0:
                raise ValueError("Invalid speed/countdown")
            if not math.isfinite(start_at) or start_at < 0:
                raise ValueError("Invalid start position")
            if plan.compiled_speed is not None and not math.isclose(speed, plan.compiled_speed):
                raise ValueError("播放速度已改变，请重新编译时间轴")
            scale = speed if plan.compiled_speed is None else 1.0
            previous = 0.0
            for action in plan.actions:
                if not math.isfinite(action.time) or action.time < previous or action.kind not in (
                    "key_down", "key_up", "mouse_down", "mouse_up"
                ):
                    raise ValueError("Invalid absolute action timeline")
                previous = action.time
            if not math.isfinite(plan.duration) or plan.duration < max(0, previous):
                raise ValueError("Invalid duration")
            self.speed, self.base = scale, start_at
            self.duration = start_at + plan.duration
            self.origin = self.clock() + delay
            self.state = "countdown"
            if not self._until(self.origin):
                return
            if self.before_play:
                self.before_play()
            # Diagnostics must not consume the initial modifier lead-in.
            self.origin = self.clock()
            self.state = "playing"
            key_down_at = {}
            last_key_up = last_mouse = float("-inf")
            for action in plan.actions:
                target = self.origin + action.time / scale
                deadline = target
                if plan.timing:
                    if action.kind == "key_down":
                        deadline = max(deadline, last_key_up + plan.timing.gap, last_mouse + plan.timing.lead)
                    elif action.kind == "key_up" and action.value in key_down_at:
                        deadline = max(deadline, key_down_at[action.value] + plan.timing.hold)
                    elif action.kind.startswith("mouse_"):
                        deadline = max(deadline, last_key_up + plan.timing.tail)
                if not self._until(deadline):
                    return
                lateness = self.clock() - target
                self.max_lateness = max(self.max_lateness, lateness)
                if plan.timing and lateness > 0.250:
                    raise RuntimeError("调度已落后超过 250 ms，已停止以避免挤在一起补发。请降低倍速或减少后台负载")
                getattr(self.backend, action.kind)(action.value)
                actual = self.clock()
                if action.kind == "key_down":
                    key_down_at[action.value] = actual
                elif action.kind == "key_up":
                    key_down_at.pop(action.value, None)
                    last_key_up = actual
                else:
                    last_mouse = actual
            if self._until(self.origin + plan.duration / scale):
                self.state = "completed"
        except BaseException as exc:
            self.error = exc
            self.state = "error"
        finally:
            try:
                self.backend.release_all()
            except BaseException as exc:
                self.release_failed = True
                self.error = BaseExceptionGroup("Playback/release failure", [self.error, exc]) if self.error else exc
                self.state = "error"
            if self.state not in ("completed", "error"):
                self.state = "stopped"
            self.done.set()

    def stop(self, timeout: float = 2.0) -> bool:
        self.cancel.set()
        if self.thread:
            self.thread.join(timeout)
            return not self.thread.is_alive()
        return True

    def retry_release(self) -> None:
        if self.thread and self.thread.is_alive():
            raise RuntimeError("Worker still owns the input backend")
        self.backend.release_all()
        self.release_failed = False
