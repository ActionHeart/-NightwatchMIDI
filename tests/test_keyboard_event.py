"""Pure in-memory ABI encoding checks. No backend or Windows DLL is created."""
import ctypes

import pytest
from nightwatch_midi.input.sendinput import INPUT, keyboard_event


@pytest.mark.parametrize("up, flags", [(False, 0x0008), (True, 0x000A)])
def test_scan_code_encoding(up, flags):
    event = keyboard_event(90, up, 0x2C)
    assert event.type == 1
    assert event.ki.wVk == 0
    assert event.ki.wScan == 0x2C
    assert event.ki.dwFlags == flags


@pytest.mark.parametrize("up, flags", [(False, 0x0009), (True, 0x000B)])
def test_extended_scan_code(up, flags):
    event = keyboard_event(0x27, up, 0xE04D)
    assert event.ki.wScan == 0x4D
    assert event.ki.dwFlags == flags


@pytest.mark.parametrize("up, flags", [(False, 0), (True, 2)])
def test_virtual_key_mode(up, flags):
    event = keyboard_event(90, up)
    assert event.ki.wVk == 90
    assert event.ki.wScan == 0
    assert event.ki.dwFlags == flags


@pytest.mark.parametrize("scan_code", [0, 0xE11D, 0xE000])
def test_invalid_scan_code(scan_code):
    with pytest.raises(ValueError):
        keyboard_event(90, False, scan_code)


def test_input_abi_size():
    assert ctypes.sizeof(INPUT) == (40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28)
