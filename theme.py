"""Shared colours and Qt styling for the pet, bubbles and chat window."""

from __future__ import annotations

from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QApplication

FONT_FAMILY = "Microsoft YaHei UI"

PINE = "#214536"
GREEN = "#2F6B4F"
GREEN_HOVER = "#3D7D5E"
LEAF = "#A9D67A"
LIME = "#DDF4C2"
CREAM = "#FFF9EC"
PAPER = "#F4EFE2"
CARD = "#FFFDF7"
INK = "#24352B"
MUTED = "#7C887D"
BORDER = "#D8D0BD"
DANGER = "#B84A4A"

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
