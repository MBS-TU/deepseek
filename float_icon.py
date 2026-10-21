"""The floating 325 badge shown while the pet is hidden."""

from __future__ import annotations

import math
import time

from PySide6.QtCore import QEasingCurve, QPoint, QPointF, QPropertyAnimation, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor, QFont, QGuiApplication, QPainter, QPen,
)
from PySide6.QtWidgets import QMenu, QWidget

from theme import (
    BORDER, CARD, FONT_FAMILY, GREEN, LIME, MENU_QSS, PINE,
)


class FloatBadge(QWidget):
    restored = Signal()
    close_requested = Signal()

    def __init__(self):
        super().__init__(None)
        self.setWindowFlags(
            Qt.Tool
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFixedSize(102, 66)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("点击唤醒牢周，右键更多")

        self._hover = False
        self._phase = 0.0
        self._last = time.perf_counter()
        self._font = QFont(FONT_FAMILY)
        self._font.setPointSize(17)
        self._font.setBold(True)

        self._pulse = QTimer(self)
        self._pulse.timeout.connect(self._on_pulse)
        self._pulse.setInterval(50)

        self._fade = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade.setDuration(160)
        self._fade.setEasingCurve(QEasingCurve.OutCubic)

    def show_at(self, point: QPoint) -> None:
        screen = QGuiApplication.screenAt(point) or QGuiApplication.primaryScreen()
        area = screen.availableGeometry()
        x = max(area.left() + 8, min(point.x(), area.right() - self.width() - 8))
        y = max(area.top() + 8, min(point.y(), area.bottom() - self.height() - 8))
        self.move(x, y)
        self._last = time.perf_counter()
        self.setWindowOpacity(0.0)
        self.show()
        self.raise_()
        self._pulse.start()
        self._fade.stop()
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.start()

    def hide_badge(self) -> None:
        self._pulse.stop()
        self.hide()

    def _on_pulse(self) -> None:
        now = time.perf_counter()
        self._last = now
        self._phase = (self._phase + 0.08) % (math.pi * 2)
        self.update()

    def enterEvent(self, event) -> None:
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)

        body = QRectF(8, 8, self.width() - 16, 46)
        glow_alpha = 26 + int(20 * (0.5 + 0.5 * math.sin(self._phase)))
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(47, 107, 79, glow_alpha))
        painter.drawRoundedRect(body.adjusted(-3, -3, 3, 3), 18, 18)

        painter.setBrush(QColor(18, 35, 25, 38))
        painter.drawRoundedRect(body.translated(0, 4), 16, 16)

        painter.setPen(QPen(QColor(PINE if self._hover else BORDER), 2.0))
        painter.setBrush(QColor(CARD))
        painter.drawRoundedRect(body, 16, 16)

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(GREEN if self._hover else LIME))
        painter.drawEllipse(QPointF(24, 31), 4, 4)

        painter.setFont(self._font)
        painter.setPen(QColor(PINE))
        painter.drawText(body.adjusted(12, 0, 0, 0), Qt.AlignCenter, "325")
        painter.end()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.hide_badge()
            self.restored.emit()
        elif event.button() == Qt.RightButton:
            self._show_menu(event.globalPosition().toPoint())
        event.accept()

    def _show_menu(self, global_pos: QPoint) -> None:
        menu = QMenu(self)
        menu.setStyleSheet(MENU_QSS)
        act_show = menu.addAction("唤醒牢周")
        menu.addSeparator()
        act_close = menu.addAction("关闭桌宠")
        chosen = menu.exec(global_pos)
        if chosen == act_show:
            self.hide_badge()
            self.restored.emit()
        elif chosen == act_close:
            self.close_requested.emit()
