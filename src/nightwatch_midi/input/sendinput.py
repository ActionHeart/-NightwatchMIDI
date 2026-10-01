"""Documented Win32 SendInput ABI only. Importing does not load user32."""
import ctypes
import sys

from .backend import InputBackend
from ..mapping.profile import InstrumentProfile

DWORD = ctypes.c_uint32
WORD = ctypes.c_uint16
LONG = ctypes.c_int32
ULONG_PTR = ctypes.c_size_t


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", LONG), ("dy", LONG), ("mouseData", DWORD),
                ("dwFlags", DWORD), ("time", DWORD), ("dwExtraInfo", ULONG_PTR)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", WORD), ("wScan", WORD), ("dwFlags", DWORD),
                ("time", DWORD), ("dwExtraInfo", ULONG_PTR)]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", DWORD), ("wParamL", WORD), ("wParamH", WORD)]


class INPUTUNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("payload",)
    _fields_ = [("type", DWORD), ("payload", INPUTUNION)]


def keyboard_event(virtual_key: int, up: bool, scan_code: int | None = None) -> INPUT:
    """Build an event in memory only; no Windows API calls."""
    event = INPUT(type=1)
    flags = 0x0002 if up else 0
    if scan_code is None:
        event.ki = KEYBDINPUT(wVk=virtual_key, dwFlags=flags)
    else:
        prefix = scan_code >> 8
        if not scan_code & 0xFF or prefix not in (0, 0xE0):
            raise ValueError("Unsupported scan code; use virtual-key mode for this profile")
        flags |= 0x0008  # KEYEVENTF_SCANCODE
        if prefix == 0xE0:
            flags |= 0x0001  # KEYEVENTF_EXTENDEDKEY
        event.ki = KEYBDINPUT(wVk=0, wScan=scan_code & 0xFF, dwFlags=flags)
    return event


class SendInputBackend(InputBackend):
    # OS mouse flags, not instrument mappings.
    _mouse_flags = {"left": (0x0002, 0x0004), "middle": (0x0020, 0x0040), "right": (0x0008, 0x0010)}

    def __init__(self, profile: InstrumentProfile, keyboard_mode: str = "scan_code") -> None:
        if keyboard_mode not in ("scan_code", "virtual_key"):
            raise ValueError("Unknown keyboard mode")
        if sys.platform != "win32":
            raise OSError("SendInput requires Windows")
        self.profile = profile
        self._user32 = ctypes.WinDLL("user32", use_last_error=True)
        self._send_input = self._user32.SendInput
        self._send_input.argtypes = [ctypes.c_uint, ctypes.POINTER(INPUT), ctypes.c_int]
        self._send_input.restype = ctypes.c_uint
        self._scan_codes: dict[str, int] = {}
        if keyboard_mode == "scan_code":
            map_key = self._user32.MapVirtualKeyW
            map_key.argtypes = [ctypes.c_uint, ctypes.c_uint]
            map_key.restype = ctypes.c_uint
            # Convert profile bindings once: down and up retain identical codes
            # even if the keyboard layout changes while an input is held.
            for key, virtual_key in profile.keys.items():
                scan_code = map_key(virtual_key, 4)  # MAPVK_VK_TO_VSC_EX
                keyboard_event(virtual_key, False, scan_code)  # Validate before any input.
                self._scan_codes[key] = scan_code

    def _send(self, event: INPUT) -> None:
        ctypes.set_last_error(0)
        if self._send_input(1, ctypes.byref(event), ctypes.sizeof(INPUT)) != 1:
            raise OSError(ctypes.get_last_error(), "SendInput failed (possibly UIPI/target privilege restriction)")

    def _key(self, key: str, up: bool) -> None:
        event = keyboard_event(self.profile.keys[key], up, self._scan_codes.get(key))
        self._send(event)

    def _mouse(self, button: str, up: bool) -> None:
        if button not in self.profile.mouse_buttons:
            raise ValueError("Mouse button not in profile")
        event = INPUT(type=0)
        event.mi = MOUSEINPUT(dwFlags=self._mouse_flags[button][int(up)])
        self._send(event)

    def key_down(self, key: str) -> None:
        self._key(key, False)

    def key_up(self, key: str) -> None:
        self._key(key, True)

    def mouse_down(self, button: str) -> None:
        self._mouse(button, False)

    def mouse_up(self, button: str) -> None:
        self._mouse(button, True)

    def release_all(self) -> None:
        # Release the full profile, including any down whose delivery was uncertain.
        errors = []
        for action, values in ((self.key_up, self.profile.keys), (self.mouse_up, self.profile.mouse_buttons)):
            for value in values:
                try:
                    action(value)
                except Exception as exc:
                    errors.append(exc)
        if errors:
            raise ExceptionGroup("Some inputs could not be released; retry Emergency Stop", errors)
