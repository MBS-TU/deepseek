"""Shared colours and Qt styling for the pet, bubbles and chat window."""

from __future__ import annotations

from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QApplication

FONT_FAMILY = "Microsoft YaHei UI"

PINE = "#183A55"
GREEN = "#2F7FB6"
GREEN_HOVER = "#3E96CE"
LEAF = "#CBEAFB"
LIME = "#E2F4FF"
CREAM = "#F5FBFF"
PAPER = "#EEF7FD"
CARD = "#FBFDFF"
INK = "#20394B"
MUTED = "#728A9B"
BORDER = "#C9DFEC"
DANGER = "#BE5049"

MENU_QSS = f"""
QMenu {{
    background: {CARD};
    color: {INK};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 6px;
    font-family: "{FONT_FAMILY}";
    font-size: 13px;
}}
QMenu::item {{
    padding: 8px 30px 8px 18px;
    border-radius: 6px;
    margin: 1px 3px;
}}
QMenu::item:selected {{
    background: {LIME};
    color: {PINE};
}}
QMenu::item:disabled {{
    color: #B6BCB4;
}}
QMenu::separator {{
    height: 1px;
    background: {BORDER};
    margin: 6px 10px;
}}
"""


def font(size: int = 10, bold: bool = False) -> QFont:
    f = QFont(FONT_FAMILY)
    f.setPointSize(size)
    f.setBold(bold)
    return f


def setup_application(app: QApplication) -> None:
    app.setStyle("Fusion")
    app.setFont(font(10))
    app.setStyleSheet(f"""
        QToolTip {{
            background: {CARD};
            color: {INK};
            border: 1px solid {BORDER};
            border-radius: 6px;
            padding: 6px 8px;
            font-family: "{FONT_FAMILY}";
        }}
    """)


def qcolor(value: str, alpha: int | None = None) -> QColor:
    color = QColor(value)
    if alpha is not None:
        color.setAlpha(alpha)
    return color
