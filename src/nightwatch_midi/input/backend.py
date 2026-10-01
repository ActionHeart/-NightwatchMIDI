from abc import ABC, abstractmethod


class InputBackend(ABC):
    @abstractmethod
    def key_down(self, key: str) -> None: ...

    @abstractmethod
    def key_up(self, key: str) -> None: ...

    @abstractmethod
    def mouse_down(self, button: str) -> None: ...

    @abstractmethod
    def mouse_up(self, button: str) -> None: ...

    @abstractmethod
    def release_all(self) -> None:
        """Attempt every release, even if another release fails."""


class MockInputBackend(InputBackend):
    """In-memory events only; never touches the desktop."""

    def __init__(self) -> None:
        self.events: list[tuple[str, str]] = []
        self.held_keys: set[str] = set()
        self.held_buttons: set[str] = set()

    def key_down(self, key: str) -> None:
        self.events.append(("key_down", key))
        self.held_keys.add(key)

    def key_up(self, key: str) -> None:
        self.events.append(("key_up", key))
        self.held_keys.discard(key)

    def mouse_down(self, button: str) -> None:
        self.events.append(("mouse_down", button))
        self.held_buttons.add(button)

    def mouse_up(self, button: str) -> None:
        self.events.append(("mouse_up", button))
        self.held_buttons.discard(button)

    def release_all(self) -> None:
        for key in sorted(self.held_keys):
            self.key_up(key)
        for button in sorted(self.held_buttons):
            self.mouse_up(button)
        self.events.append(("release_all", ""))
