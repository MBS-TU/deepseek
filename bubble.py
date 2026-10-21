"""The small cream speech bubble that pops above the pet."""

from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve, QPoint, QPropertyAnimation, QRectF, Qt, QTimer,
)
from PySide6.QtGui import (
    QColor, QFont, QFontMetrics, QGuiApplication, QPainter, QPainterPath, QPen,
)
from PySide6.QtWidgets import QWidget

from theme import CREAM, FONT_FAMILY, GREEN, PINE


class Bubble(QWidget):
    def __init__(self):
        super().__init__(None)
        self.setWindowFlags(
            Qt.Tool
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.WindowTransparentForInput
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self._text = "325"
        self._font = QFont(FONT_FAMILY)
        self._font.setPointSize(19)
        self._font.setBold(True)

        self._fade = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade.setDuration(130)
        self._fade.setEasingCurve(QEasingCurve.OutCubic)
        self._fade.finished.connect(self._on_fade_finished)

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._fade_out)

        self.resize(112, 84)

    def _build_path(self) -> QPainterPath:
        body = QRectF(8, 6, self.width() - 16, self.height() - 34)
        path = QPainterPath()
        path.addRoundedRect(body, 16, 16)
        cx = self.width() / 2
        tail = QPainterPath()
        tail.moveTo(cx - 10, body.bottom() - 1)
        tail.lineTo(cx, body.bottom() + 13)
        tail.lineTo(cx + 10, body.bottom() - 1)
        tail.closeSubpath()
        return path.united(tail)

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)

        path = self._build_path()

        painter.save()
        painter.translate(0, 3)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(18, 35, 25, 34))
        painter.drawPath(path)
        painter.restore()

        painter.setPen(QPen(QColor(PINE), 2.2))
        painter.setBrush(QColor(CREAM))
        painter.drawPath(path)

        # A tiny green accent dot keeps the bubble tied to the pet's colours.
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(GREEN))
        painter.drawEllipse(QPoint(24, 23), 3.4, 3.4)

        painter.setFont(self._font)
        painter.setPen(QColor(PINE))
        body = QRectF(8, 6, self.width() - 16, self.height() - 34)
        painter.drawText(body, Qt.AlignCenter, self._text)
        painter.end()

    def show_text(self, text: str, anchor: QPoint) -> None:
        self._text = text
        metrics = QFontMetrics(self._font)
        width = max(108, metrics.horizontalAdvance(text) + 64)
        self.resize(width, 84)

        screen = QGuiApplication.screenAt(anchor) or QGuiApplication.primaryScreen()
        area = screen.availableGeometry()
        x = anchor.x() - self.width() // 2
        y = anchor.y() - self.height() + 6
        x = max(area.left() + 8, min(x, area.right() - self.width() - 8))
        y = max(area.top() + 8, min(y, area.bottom() - self.height() - 8))
        self.move(x, y)

        self._fade.stop()
        self._hide_timer.stop()
        self.setWindowOpacity(0.0)
        self.show()
        self.raise_()
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.setDuration(130)
        self._fade.start()
        self._hide_timer.start(1150)

    def hide_now(self) -> None:
        self._fade.stop()
        self._hide_timer.stop()
        self.hide()

    def _fade_out(self) -> None:
        self._fade.stop()
        self._fade.setStartValue(self.windowOpacity())
        self._fade.setEndValue(0.0)
        self._fade.setDuration(200)
        self._fade.start()

    def _on_fade_finished(self) -> None:
        if self.windowOpacity() <= 0.01:
            self.hide()
