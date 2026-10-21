"""Frame player with a soft cross-fade between the pet's four states."""

from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import QObject, QRectF, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap

from paths import asset_path
from theme import GREEN, PINE


STATE_INTERVALS_MS = {
    "idle": 130,
    "mouse": 90,
    "key": 75,
    "drag": 100,
}
TRANSITION_SECONDS = 0.16


class Animator(QObject):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current = "idle"
        self.index = 0
        self._accum_ms = 0.0
        self._transition = 1.0
        self._previous_pixmap: QPixmap | None = None
        self._last_tick = time.perf_counter()
        self.frames = {
            state: self._load_state(asset_path(state))
            for state in STATE_INTERVALS_MS
        }

        self._timer = QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def _load_state(self, folder: Path) -> list[QPixmap]:
        frames: list[QPixmap] = []
        if folder.is_dir():
            for path in sorted(folder.glob("*.png")):
                pix = QPixmap(str(path))
                if not pix.isNull():
                    frames.append(pix)
        return frames or [self._placeholder()]

    @staticmethod
    def _placeholder() -> QPixmap:
        pix = QPixmap(700, 720)
        pix.fill(Qt.transparent)
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor(GREEN))
        painter.setPen(QPen(QColor(PINE), 8))
        painter.drawRoundedRect(QRectF(110, 140, 480, 440), 80, 80)
        painter.setPen(QColor("white"))
        font = QFont("Microsoft YaHei UI")
        font.setPointSize(64)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(QRectF(110, 140, 480, 440), Qt.AlignCenter, "deep")
        painter.end()
        return pix

    def set_state(self, state: str) -> None:
        if state not in self.frames:
            state = "idle"
        if state == self.current:
            return
        self._previous_pixmap = self.frames[self.current][self.index]
        self.current = state
        self.index = 0
        self._accum_ms = 0.0
        self._transition = 0.0
        self.changed.emit()

    def _tick(self) -> None:
        now = time.perf_counter()
        dt = min(0.2, max(0.0, now - self._last_tick))
        self._last_tick = now

        needs_repaint = False
        if self._transition < 1.0:
            self._transition = min(1.0, self._transition + dt / TRANSITION_SECONDS)
            needs_repaint = True

        interval = STATE_INTERVALS_MS.get(self.current, 120)
        self._accum_ms += dt * 1000.0
        advanced = False
        while self._accum_ms >= interval:
            self._accum_ms -= interval
            self.index = (self.index + 1) % len(self.frames[self.current])
            advanced = True

        if advanced or needs_repaint:
            self.changed.emit()

    def paint_frames(self) -> tuple[QPixmap | None, QPixmap, float]:
        """Return (outgoing, incoming, blend)."""
        current = self.frames[self.current][self.index]
        if self._previous_pixmap is None or self._transition >= 1.0:
            return None, current, 1.0
        t = self._transition
        eased = t * t * (3.0 - 2.0 * t)
        return self._previous_pixmap, current, eased

    def paint(self, painter: QPainter, rect) -> None:
        """Draw the current frame scaled to the widget rectangle."""
        previous, current, blend = self.paint_frames()
        painter.save()
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        if previous is not None and blend < 1.0:
            painter.setOpacity(1.0 - blend)
            painter.drawPixmap(rect, previous)
        painter.setOpacity(blend)
        painter.drawPixmap(rect, current)
        painter.restore()
