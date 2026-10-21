"""Independent streaming chat window connected to DeepSeek V4.1 Flash."""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication, QIcon, QKeyEvent, QPixmap
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QSizePolicy, QTextEdit, QVBoxLayout, QWidget,
)

from api_client import ChatThread, MODEL_DISPLAY_NAME, MODEL_ID, SYSTEM_PROMPT
from api_settings import ApiSettingsDialog
from config_util import has_api_key, load_config
from paths import asset_path
from runtime_state import runtime
from theme import (
    BORDER, CARD, DANGER, FONT_FAMILY, GREEN, GREEN_HOVER, INK,
    MUTED, PAPER, PINE,
)

log = logging.getLogger(__name__)

MAX_HISTORY_MESSAGES = 18


HARNESS_QSS = f"""
QDialog {{ background: {PAPER}; color: {INK}; font-family: "{FONT_FAMILY}"; }}
QFrame#header {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 {PINE}, stop:1 {GREEN});
    border: none;
}}
QLabel#headerTitle {{ color: white; font-size: 18px; font-weight: 700; }}
QLabel#headerSub {{ color: #CFE2D3; font-size: 10px; }}
QPushButton#headerButton {{
    color: white;
    background: rgba(255,255,255,26);
    border: 1px solid rgba(255,255,255,60);
    border-radius: 9px;
    padding: 7px 13px;
    font-size: 12px;
}}
QPushButton#headerButton:hover {{ background: rgba(255,255,255,52); }}
QPushButton#headerButton:disabled {{ color: rgba(255,255,255,100); }}
QScrollArea {{ border: none; background: {PAPER}; }}
QWidget#messageHost {{ background: {PAPER}; }}
QFrame#assistantBubble {{
    background: {CARD};
    border: 1px solid #E2DAC8;
    border-radius: 15px;
    border-bottom-left-radius: 5px;
}}
QFrame#userBubble {{
    background: {GREEN};
    border: 1px solid {GREEN};
    border-radius: 15px;
    border-bottom-right-radius: 5px;
}}
QFrame#errorBubble {{
    background: #FFF1ED;
    border: 1px solid #E8B7AA;
    border-radius: 13px;
}}
QLabel#bubbleName {{ color: {MUTED}; font-size: 10px; }}
QLabel#bubbleText {{ color: {INK}; font-size: 10.5pt; background: transparent; }}
QFrame#userBubble QLabel#bubbleName {{ color: #CFE4D2; }}
QFrame#userBubble QLabel#bubbleText {{ color: white; }}
QFrame#errorBubble QLabel#bubbleText {{ color: #8E3E32; }}
QFrame#composer {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 16px;
}}
QTextEdit#chatInput {{
    background: transparent;
    border: none;
    color: {INK};
    font-size: 12.5pt;
    padding: 4px 2px;
}}
QPushButton#sendButton {{
    background: {GREEN};
    color: white;
    border: none;
    border-radius: 12px;
    padding: 10px 22px;
    font-size: 12px;
    font-weight: 700;
}}
QPushButton#sendButton:hover {{ background: {GREEN_HOVER}; }}
QPushButton#sendButton:disabled {{ background: #AFC2B4; color: #EEF3EF; }}
QLabel#statusLabel {{ font-size: 10.5px; color: {MUTED}; }}
QLabel#footerHint {{ font-size: 10px; color: #929B90; }}
QScrollBar:vertical {{ background: transparent; width: 9px; margin: 4px 2px; }}
QScrollBar::handle:vertical {{ background: #C8C0AE; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: #AFA793; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
"""


class ChatInput(QTextEdit):
    send_requested = Signal()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and not (
            event.modifiers() & Qt.ShiftModifier
        ):
            self.send_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class HarnessDialog(QDialog):
    config_changed = Signal(dict)

    def __init__(self, cfg: dict | None = None, pet=None):
        super().__init__(None)
        self.setWindowTitle("牢周 · DeepSeek Harness")
        self.setWindowIcon(QIcon(str(asset_path("icon.ico"))))
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.setMinimumSize(560, 600)
        self.resize(650, 700)
        self.setStyleSheet(HARNESS_QSS)

        self.cfg = dict(cfg) if cfg is not None else load_config()
        self.pet = pet
        self.history: list[dict] = []
        self._thread: Optional[ChatThread] = None
        self._generating = False
        self._placed = False
        self._assistant_label: QLabel | None = None
        self._assistant_container: QWidget | None = None
        self._assistant_content = ""
        self._reasoning_content = ""
        self._typing_base = "正在思考"
        self._typing_step = 0
        self._typing_timer = QTimer(self)
        self._typing_timer.setInterval(380)
        self._typing_timer.timeout.connect(self._tick_typing)

        self._build_ui()
        self._show_welcome()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QFrame()
        header.setObjectName("header")
        header.setFixedHeight(88)
        h = QHBoxLayout(header)
        h.setContentsMargins(22, 14, 20, 14)
        h.setSpacing(12)

        avatar = QLabel()
        pix = QPixmap(str(asset_path("icon.png")))
        if not pix.isNull():
            avatar.setPixmap(pix.scaled(48, 48, Qt.KeepAspectRatio,
                                        Qt.SmoothTransformation))
        avatar.setFixedSize(48, 48)
        h.addWidget(avatar)

        titles = QVBoxLayout()
        titles.setSpacing(0)
        title = QLabel("牢周 · Harness")
        title.setObjectName("headerTitle")
        subtitle = QLabel(f"独立对话窗 · {MODEL_DISPLAY_NAME}")
        subtitle.setObjectName("headerSub")
        titles.addWidget(title)
        titles.addWidget(subtitle)
        h.addLayout(titles)
        h.addStretch(1)

        self.admin_btn = QPushButton("后台")
        self.admin_btn.setObjectName("headerButton")
        self.admin_btn.clicked.connect(self._open_admin)
        h.addWidget(self.admin_btn)

        self.new_btn = QPushButton("新对话")
        self.new_btn.setObjectName("headerButton")
        self.new_btn.clicked.connect(self.new_conversation)
        h.addWidget(self.new_btn)

        self.settings_btn = QPushButton("设置")
        self.settings_btn.setObjectName("headerButton")
        self.settings_btn.clicked.connect(self.open_settings)
        h.addWidget(self.settings_btn)
        root.addWidget(header)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.messages_host = QWidget()
        self.messages_host.setObjectName("messageHost")
        self.messages_layout = QVBoxLayout(self.messages_host)
        self.messages_layout.setContentsMargins(20, 18, 20, 18)
        self.messages_layout.setSpacing(13)
        self.messages_layout.addStretch(1)
        self.scroll.setWidget(self.messages_host)
        root.addWidget(self.scroll, 1)

        footer = QWidget()
        footer_layout = QVBoxLayout(footer)
        footer_layout.setContentsMargins(20, 10, 20, 16)
        footer_layout.setSpacing(8)

        status_row = QHBoxLayout()
        status_row.setContentsMargins(3, 0, 3, 0)
        self.status_label = QLabel()
        self.status_label.setObjectName("statusLabel")
        status_row.addWidget(self.status_label)
        status_row.addStretch(1)
        self.model_label = QLabel(self.cfg.get("model", MODEL_ID))
        self.model_label.setObjectName("footerHint")
        status_row.addWidget(self.model_label)
        footer_layout.addLayout(status_row)

        composer = QFrame()
        composer.setObjectName("composer")
        comp = QHBoxLayout(composer)
        comp.setContentsMargins(14, 8, 8, 8)
        comp.setSpacing(8)
        self.input = ChatInput()
        self.input.setObjectName("chatInput")
        self.input.setPlaceholderText("跟牢周说点什么…  Enter 发送 / Shift+Enter 换行")
        self.input.setFixedHeight(62)
        self.input.send_requested.connect(self._on_send_clicked)
        comp.addWidget(self.input, 1)

        self.send_btn = QPushButton("发送")
        self.send_btn.setObjectName("sendButton")
        self.send_btn.setCursor(Qt.PointingHandCursor)
        self.send_btn.setMinimumWidth(84)
        self.send_btn.clicked.connect(self._on_send_clicked)
        comp.addWidget(self.send_btn)
        footer_layout.addWidget(composer)

        hint_row = QHBoxLayout()
        hint_row.setContentsMargins(3, 0, 3, 0)
        hint = QLabel("Enter 发送 · Shift+Enter 换行")
        hint.setObjectName("footerHint")
        hint_row.addWidget(hint)
        hint_row.addStretch(1)
        self.config_hint = QLabel("")
        self.config_hint.setObjectName("footerHint")
        hint_row.addWidget(self.config_hint)
        footer_layout.addLayout(hint_row)
        root.addWidget(footer)

        self._refresh_status()

    def _refresh_status(self) -> None:
        if has_api_key(self.cfg):
            self._set_status(f"● 已配置 · {self.cfg.get('model', MODEL_ID)}", GREEN)
        else:
            self._set_status("○ 还没有配置 API Key", DANGER)
        self.model_label.setText(self.cfg.get("model", MODEL_ID))

    def _set_status(self, text: str, color: str = MUTED) -> None:
        self.status_label.setStyleSheet(f"color: {color}; font-size: 10.5px;")
        self.status_label.setText(text)

    # ------------------------------------------------------------- messages
    def _show_welcome(self) -> None:
        self._add_message(
            "assistant",
            "我是牢周。今天想聊点什么？\n\n"
            "右键我，可以把我藏成 325；右上角「后台」能改我的人设、"
            "看运行状态和思考过程。",
            welcome=True,
        )

    def _clear_messages(self) -> None:
        while self.messages_layout.count() > 1:
            item = self.messages_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
            else:
                child = item.layout()
                if child is not None:
                    self._delete_layout(child)
        self._show_welcome()

    @staticmethod
    def _delete_layout(layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
            elif item.layout() is not None:
                HarnessDialog._delete_layout(item.layout())

    def _add_message(self, role: str, text: str, welcome: bool = False,
                     error: bool = False) -> tuple[QWidget, QLabel]:
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        if role == "assistant":
            avatar = QLabel()
            pix = QPixmap(str(asset_path("icon.png")))
            if not pix.isNull():
                avatar.setPixmap(pix.scaled(28, 28, Qt.KeepAspectRatio,
                                            Qt.SmoothTransformation))
            avatar.setFixedSize(28, 28)
            row.addWidget(avatar, 0, Qt.AlignTop)
        elif role == "user":
            row.addStretch(1)

        bubble = QFrame()
        bubble.setObjectName("errorBubble" if error else
                             ("userBubble" if role == "user" else "assistantBubble"))
        bubble.setMaximumWidth(540)
        bubble.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Minimum)
        b = QVBoxLayout(bubble)
        b.setContentsMargins(13, 9, 13, 10)
        b.setSpacing(2)

        name = "牢周" if role == "assistant" else "你"
        if error:
            name = "连接提示"
        name_label = QLabel(name)
        name_label.setObjectName("bubbleName")
        if role == "user":
            name_label.setAlignment(Qt.AlignRight)
        b.addWidget(name_label)

        content = QLabel()
        content.setObjectName("bubbleText")
        content.setWordWrap(True)
        content.setOpenExternalLinks(True)
        content.setTextInteractionFlags(
            Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse
        )
        content.setMaximumWidth(510)
        if role == "assistant" and not welcome:
            content.setTextFormat(Qt.MarkdownText)
        else:
            content.setTextFormat(Qt.PlainText)
        content.setText(text)
        b.addWidget(content)

        row.addWidget(bubble, 0, Qt.AlignTop)
        if role == "assistant":
            row.addStretch(1)

        self.messages_layout.insertWidget(self.messages_layout.count() - 1, container)
        QTimer.singleShot(0, self._scroll_to_bottom)
        return container, content

    def _remove_message(self, container: QWidget) -> None:
        for index in range(self.messages_layout.count()):
            item = self.messages_layout.itemAt(index)
            if item.widget() is container:
                self.messages_layout.takeAt(index)
                container.setParent(None)
                container.deleteLater()
                break

    def _scroll_to_bottom(self) -> None:
        bar = self.scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _start_typing(self, label: QLabel) -> None:
        self._assistant_label = label
        self._typing_step = 0
        self._typing_base = "正在思考"
        label.setText(self._typing_base)
        self._typing_timer.start()

    def _tick_typing(self) -> None:
        if self._assistant_label is None or self._assistant_content:
            self._typing_timer.stop()
            return
        self._typing_step = (self._typing_step + 1) % 4
        self._assistant_label.setText(self._typing_base + "…" + "·" * self._typing_step)
        self._scroll_to_bottom()

    def _stop_typing(self) -> None:
        self._typing_timer.stop()

    # ----------------------------------------------------------------- chat
    def _on_send_clicked(self) -> None:
        if self._generating:
            self._stop_generation()
        else:
            self.send_message()

    def send_message(self) -> None:
        if self._generating:
            return
        text = self.input.toPlainText().strip()
        if not text:
            return

        # Pick up persona/API changes saved from the admin window.
        self.cfg = load_config()
        self._refresh_status()
        if not has_api_key(self.cfg):
            self._add_message("assistant",
                              "还没有配置 DeepSeek API Key。点右上角“设置”连一下。",
                              error=True)
            self.open_settings()
            return

        self.input.clear()
        self.history.append({"role": "user", "content": text})
        self.history = self.history[-MAX_HISTORY_MESSAGES:]
        self._add_message("user", text)

        container, label = self._add_message("assistant", "")
        self._assistant_container = container
        self._assistant_label = label
        self._assistant_content = ""
        self._reasoning_content = ""
        self._start_typing(label)

        self._set_generating(True)
        self._set_status("● 牢周正在思考…", GREEN)
        runtime.begin_turn(text, self.cfg.get("model", MODEL_ID))

        persona = (self.cfg.get("persona") or "").strip() or SYSTEM_PROMPT
        messages = [{"role": "system", "content": persona}] + self.history
        thread = ChatThread(dict(self.cfg), messages)
        self._thread = thread
        thread.chunk.connect(self._on_chunk)
        thread.reasoning_chunk.connect(self._on_reasoning_chunk)
        thread.completed.connect(self._on_completed)
        thread.failed.connect(self._on_failed)
        thread.cancelled.connect(self._on_cancelled)
        thread.finished.connect(self._on_thread_finished)
        thread.start()

    def _on_reasoning_chunk(self, text: str) -> None:
        if not text:
            return
        self._reasoning_content += text
        runtime.append_reasoning(text)
        if len(self._reasoning_content) == len(text):
            self._set_status("● 牢周正在思考…", GREEN)
        QTimer.singleShot(0, self._scroll_to_bottom)

    def _on_chunk(self, text: str) -> None:
        if not text:
            return
        if not self._assistant_content:
            self._stop_typing()
            if self._assistant_label is not None:
                self._assistant_label.setText("")
        self._assistant_content += text
        runtime.mark_receiving(len(self._assistant_content))
        if self._assistant_label is not None:
            self._assistant_label.setText(self._assistant_content)
            self._assistant_label.adjustSize()
        self._set_status("● 正在接收回复…", GREEN)
        QTimer.singleShot(0, self._scroll_to_bottom)

    def _on_completed(self, text: str) -> None:
        self._stop_typing()
        if text and not self._assistant_content:
            self._assistant_content = text
            if self._assistant_label is not None:
                self._assistant_label.setText(text)
        if self._assistant_content:
            self.history.append({"role": "assistant",
                                 "content": self._assistant_content})
            self.history = self.history[-MAX_HISTORY_MESSAGES:]
            self._set_status(f"● 已连接 · {self.cfg.get('model', MODEL_ID)}", GREEN)
        else:
            self._show_error("DeepSeek 没有返回内容，再试一次吧。")
        runtime.finish_turn(len(self._assistant_content))
        self._generating = False
        QTimer.singleShot(0, self._scroll_to_bottom)

    def _on_failed(self, message: str) -> None:
        self._stop_typing()
        if self._assistant_container is not None:
            self._remove_message(self._assistant_container)
            self._assistant_container = None
            self._assistant_label = None
        self._show_error(message)
        self._set_status("● 连接出错", DANGER)
        runtime.fail_turn(message)

    def _on_cancelled(self) -> None:
        self._stop_typing()
        if self._assistant_content:
            self.history.append({"role": "assistant",
                                 "content": self._assistant_content})
            if self._assistant_label is not None:
                self._assistant_label.setText(self._assistant_content + "\n\n（已停止）")
        else:
            if self._assistant_container is not None:
                self._remove_message(self._assistant_container)
            self._assistant_container = None
            self._assistant_label = None
        self._set_status("● 已停止", MUTED)
        runtime.cancel_turn()

    def _show_error(self, message: str) -> None:
        self._add_message("assistant", message, error=True)

    def _set_generating(self, generating: bool) -> None:
        self._generating = generating
        self.send_btn.setText("停止" if generating else "发送")
        self.send_btn.setEnabled(True)
        self.new_btn.setEnabled(not generating)
        self.settings_btn.setEnabled(not generating)
        self.input.setEnabled(True)
        if not generating:
            self.input.setFocus()

    def _stop_generation(self) -> None:
        if self._thread is not None and self._thread.isRunning():
            self._thread.cancel()
            self.send_btn.setEnabled(False)
            self._set_status("● 正在停止…", MUTED)

    def _on_thread_finished(self) -> None:
        thread = self._thread
        self._thread = None
        if thread is not None:
            thread.deleteLater()
        self._generating = False
        self._stop_typing()
        self.send_btn.setText("发送")
        self.send_btn.setEnabled(True)
        self.new_btn.setEnabled(True)
        self.settings_btn.setEnabled(True)
        if self.isVisible():
            self.input.setFocus()

    # --------------------------------------------------------------- window
    def new_conversation(self) -> None:
        if self._generating:
            return
        self.history.clear()
        self._clear_messages()
        self._refresh_status()
        self.input.clear()
        self.input.setFocus()

    def open_settings(self) -> None:
        if self._generating:
            return
        dlg = ApiSettingsDialog(self.cfg, parent=self)
        accepted = dlg.exec()
        dlg.shutdown()
        if accepted:
            self.cfg = load_config()
            self._refresh_status()
            runtime.log("API", "API 设置已更新")
            self.config_changed.emit(dict(self.cfg))
            if self.isVisible():
                self.input.setFocus()

    def _open_admin(self) -> None:
        if self.pet is not None and hasattr(self.pet, "_open_admin"):
            self.pet._open_admin()
        else:
            self._set_status("● 请从桌宠右键菜单打开管理后台", MUTED)

    def ensure_api_key(self) -> bool:
        """Compatibility entry point used by PetWindow._open_harness()."""
        if has_api_key(self.cfg):
            return True
        dlg = ApiSettingsDialog(self.cfg, first_run=True, parent=None)
        accepted = dlg.exec()
        dlg.shutdown()
        if not accepted:
            return False
        self.cfg = load_config()
        self._refresh_status()
        runtime.log("API", "连接验证成功，API 已保存")
        self.config_changed.emit(dict(self.cfg))
        return True

    def show_near_pet(self) -> None:
        self._place_once()
        self.show()
        self.raise_()
        self.activateWindow()
        self.input.setFocus()

    def _place_once(self) -> None:
        if self._placed:
            return
        area = None
        if self.pet is not None:
            screen = QGuiApplication.screenAt(self.pet.frameGeometry().center())
            area = screen.availableGeometry() if screen else None
        if area is None:
            screen = QGuiApplication.primaryScreen()
            area = screen.availableGeometry()
        width = min(650, max(560, area.width() - 80))
        height = min(700, max(580, area.height() - 90))
        self.resize(width, height)
        x = area.left() + (area.width() - width) // 2
        y = area.top() + 40
        if self.pet is not None:
            candidate = self.pet.frameGeometry().left() - width - 18
            if candidate >= area.left() + 12:
                x = candidate
                y = max(area.top() + 12,
                        min(self.pet.frameGeometry().top(),
                            area.bottom() - height - 40))
        x = max(area.left() + 8, min(x, area.right() - width - 8))
        y = max(area.top() + 8, min(y, area.bottom() - height - 40))
        self.move(x, y)
        self._placed = True

    def showEvent(self, event) -> None:
        self._place_once()
        super().showEvent(event)
        QTimer.singleShot(0, self.input.setFocus)

    def closeEvent(self, event) -> None:
        if self._thread is not None and self._thread.isRunning():
            self._thread.cancel()
        event.accept()

    def shutdown(self) -> None:
        thread = self._thread
        if thread is not None and thread.isRunning():
            thread.cancel()
            if not thread.wait(2500):
                thread.terminate()
                thread.wait(500)
        self._thread = None
