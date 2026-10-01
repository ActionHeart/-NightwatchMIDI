import json
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path


@dataclass(frozen=True)
class Binding:
    key: str
    buttons: tuple[str, ...] = ()


@dataclass(frozen=True)
class InstrumentProfile:
    name: str
    keys: dict[str, int]
    mouse_buttons: tuple[str, ...]
    midi_notes: dict[str, str | dict]

    def binding(self, note: int) -> Binding | None:
        value = self.midi_notes.get(str(note))
        if value is None:
            return None
        if isinstance(value, str):
            return Binding(value)
        return Binding(value["key"], tuple(value.get("buttons", [])))


def load_profile(path: Path | None = None, *, name: str = "input_tester.json") -> InstrumentProfile:
    source = path if path is not None else files("nightwatch_midi").joinpath(f"profiles/{name}")
    data = json.loads(source.read_text(encoding="utf-8"))
    keys = data["keys"]
    if not isinstance(keys, dict) or not keys or any(
        not isinstance(k, str) or not k or type(v) is not int or not 1 <= v <= 254
        for k, v in keys.items()
    ):
        raise ValueError("keys must map nonempty names to Win32 virtual keys 1..254")
    buttons = data["mouse_buttons"]
    if not isinstance(buttons, list) or any(b not in ("left", "middle", "right") for b in buttons):
        raise ValueError("Unsupported mouse button")
    notes = data["midi_notes"]
    if not isinstance(notes, dict):
        raise ValueError("Invalid MIDI note mapping")
    for n, value in notes.items():
        if not isinstance(n, str) or not n.isdecimal() or str(int(n)) != n or not 0 <= int(n) <= 127:
            raise ValueError("Invalid MIDI note number")
        if isinstance(value, str):
            value = {"key": value}
        if not isinstance(value, dict) or value.get("key") not in keys:
            raise ValueError("Invalid MIDI key mapping")
        modifiers = value.get("buttons", [])
        if not isinstance(modifiers, list) or any(b not in buttons for b in modifiers) or len(set(modifiers)) != len(modifiers):
            raise ValueError("Invalid MIDI mouse modifiers")
    if not isinstance(data["name"], str) or not data["name"]:
        raise ValueError("Profile requires a name")
    return InstrumentProfile(data["name"], dict(keys), tuple(dict.fromkeys(buttons)), dict(notes))
