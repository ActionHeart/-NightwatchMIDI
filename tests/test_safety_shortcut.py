from nightwatch_midi.ui.main_window import MainWindow
from nightwatch_midi.ui.safety_shortcut import SafetyShortcut


def test_hotkey_edges_fire_once_per_press(app):
    window = MainWindow()
    state = {0x78: False}
    calls = []
    shortcut = SafetyShortcut(window, lambda: True, lambda: calls.append("stop"),
                              reader=lambda: False,
                              hotkeys={0x78: lambda: calls.append("back")},
                              key_reader=lambda vk: state.get(vk, False))
    state[0x78] = True
    shortcut.poll()
    shortcut.poll()
    assert calls == ["back"]
    state[0x78] = False
    shortcut.poll()
    state[0x78] = True
    shortcut.poll()
    assert calls == ["back", "back"]
    window.close()


def test_hotkeys_not_read_while_inactive(app):
    window = MainWindow()
    reads = []
    shortcut = SafetyShortcut(window, lambda: False, window.emergency_stop,
                              reader=lambda: False,
                              hotkeys={0x78: lambda: None},
                              key_reader=lambda vk: reads.append(vk) or False)
    shortcut.poll()
    assert reads == []
    window.close()
