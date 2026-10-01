import pytest

from nightwatch_midi.game.diagnostics import format_snapshot
from nightwatch_midi.input.backend import MockInputBackend
from nightwatch_midi.input.session import InputSession


@pytest.mark.parametrize("sender,target,expected", [
    (0x2000, 0x3000, "存在 Windows UIPI 权限限制条件"),
    (0x3000, 0x3000, "未发现目标完整性级别高于测试器"),
    (None, 0x3000, "权限信息不完整"),
    (0x2000, None, "权限信息不完整"),
])
def test_permission_diagnosis(sender, target, expected):
    text = format_snapshot({
        "time": "test time", "window_title": "Test target",
        "sender": {"pid": 1, "integrity": sender, "error": "unavailable"},
        "target": {"pid": 2, "integrity": target, "error": "unavailable"},
    })
    assert expected in text
    assert "Test target" in text


def test_snapshot_runs_at_press_time_not_countdown_start():
    now = [0.0]
    backend = MockInputBackend()
    snapshots = []

    def before_press():
        assert not backend.held_keys
        snapshots.append(now[0])

    session = InputSession(backend, lambda: now[0], before_press)
    session.start(["Z"], [], 1, 5)
    assert snapshots == []
    now[0] = 5.0
    session.tick()
    assert snapshots == [5.0]
    assert backend.held_keys == {"Z"}
    session.stop()


def test_callback_failure_cleans_up():
    backend = MockInputBackend()

    def fail():
        raise RuntimeError("callback failed")

    session = InputSession(backend, before_press=fail)
    with pytest.raises(RuntimeError, match="callback failed"):
        session.start(["Z"], [], 1)
    assert session.deadline is None
    assert backend.events[-1] == ("release_all", "")
    assert not backend.held_keys
