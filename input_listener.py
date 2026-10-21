"""Global mouse/keyboard activity monitor.

Only activity is reported – key codes and typed text are intentionally never
captured or emitted.  This keeps the pet responsive without turning it into a
keylogger.
"""

from __future__ import annotations

import logging
import time

from PySide6.QtCore import QObject, Signal

log = logging.getLogger(__name__)


class InputListener(QObject):
    mouse_moved = Signal()
    key_pressed = Signal()
    failed = Signal(str)

    MOVE_THROTTLE = 0.04
    KEY_THROTTLE = 0.025

    def __init__(self, parent=None):
        super().__init__(parent)
        self._last_move = 0.0
        self._last_key = 0.0
        self._mouse_listener = None
        self._key_listener = None

    def start(self) -> bool:
        try:
            from pynput import keyboard, mouse

            self._mouse_listener = mouse.Listener(on_move=self._on_move)
            self._key_listener = keyboard.Listener(on_press=self._on_key)
            self._mouse_listener.start()
            self._key_listener.start()
            return True
        except Exception as exc:  # pragma: no cover - depends on Windows hooks
            log.exception("Input listener could not start")
            self.failed.emit(str(exc))
            self.stop()
            return False

    def stop(self) -> None:
        for listener in (self._mouse_listener, self._key_listener):
            if listener is not None:
                try:
                    listener.stop()
                except Exception:
                    pass
        self._mouse_listener = None
        self._key_listener = None

    def _on_move(self, x, y) -> None:
        try:
            now = time.perf_counter()
            if now - self._last_move < self.MOVE_THROTTLE:
                return
            self._last_move = now
            self.mouse_moved.emit()
        except Exception:
            log.debug("mouse callback failed", exc_info=True)

    def _on_key(self, key) -> None:
        try:
            now = time.perf_counter()
            if now - self._last_key < self.KEY_THROTTLE:
                return
            self._last_key = now
            # Do not pass `key` along: only the fact that typing happened matters.
            self.key_pressed.emit()
        except Exception:
            log.debug("key callback failed", exc_info=True)
