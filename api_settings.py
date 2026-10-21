"""First-run API key setup / connection dialog."""

from __future__ import annotations

from PySide6.QtCore import QTimer, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QIcon
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QWidget,
)

from api_client import DEFAULT_ENDPOINT, MODEL_ID, ValidateThread, normalize_endpoint
from config_util import save_config
from paths import asset_path, config_path
from theme import (
    BORDER, CARD, DANGER, FONT_FAMILY, GREEN, GREEN_HOVER, INK, LEAF,
    MUTED, PAPER, PINE,
)

DIALOG_QSS = f"""
QDialog {{ background: {PAPER}; color: {INK}; font-family: "{FONT_FAMILY}"; }}
QLabel {{ color: {INK}; }}
QLabel#heading {{ font-size: 21px; font-weight: 700; color: {PINE}; }}
QLabel#caption {{ color: {MUTED}; font-size: 12px; }}
QLabel#fieldLabel {{ color: {PINE}; font-weight: 600; font-size: 12px; }}
QLabel#hint {{ color: {MUTED}; font-size: 11px; }}
QLineEdit, QComboBox {{
    background: {CARD};
    color: {INK};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 9px 11px;
    selection-background-color: {LEAF};
    font-size: 13px;
}}
QLineEdit:focus, QComboBox:focus {{ border: 2px solid {GREEN}; padding: 8px 10px; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QPushButton {{
    border: none;
    border-radius: 10px;
    padding: 10px 16px;
    font-weight: 600;
    font-size: 13px;
}}
QPushButton#primary {{ background: {GREEN}; color: white; }}
QPushButton#primary:hover {{ background: {GREEN_HOVER}; }}
QPushButton#primary:disabled {{ background: #AEC0B4; color: #ECF2ED; }}
QPushButton#secondary {{ background: transparent; color: {PINE}; border: 1px solid {BORDER}; }}
QPushButton#secondary:hover {{ background: {CARD}; }}
QPushButton#eye {{ background: transparent; color: {GREEN}; padding: 4px 8px; }}
QFrame#card {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 16px;
}}
"""


class ApiSettingsDialog(QDialog):
    def __init__(self, cfg: dict, first_run: bool = False, parent=None):
        super().__init__(parent)
        self.cfg = dict(cfg)
        self.first_run = first_run
        self._busy = False
        self._thread: ValidateThread | None = None
        self._pending_cfg: dict | None = None
        self.result_cfg = None

        self.setWindowTitle("连接 DeepSeek")
        self.setWindowIcon(QIcon(str(asset_path("icon.ico"))))
        self.setModal(True)
        self.setMinimumWidth(540)
        self.setStyleSheet(DIALOG_QSS)

        root = QVBoxLayout(self)
        root.setContentsMargins(26, 22, 26, 20)
        root.setSpacing(12)

        heading = QLabel("连接 DeepSeek" if not first_run else "和牢周连上线")
        heading.setObjectName("heading")
        root.addWidget(heading)

        caption = QLabel(
            "第一次使用需要配置 DeepSeek API Key，验证通过后会自动保存。"
            if first_run else
            "更新 API Key、模型或接口地址。保存前会先测试连接。"
        )
        caption.setWordWrap(True)
        caption.setObjectName("caption")
        root.addWidget(caption)

        card = QFrame()
        card.setObjectName("card")
        form = QVBoxLayout(card)
        form.setContentsMargins(18, 16, 18, 16)
        form.setSpacing(7)

        key_label = QLabel("DeepSeek API Key")
        key_label.setObjectName("fieldLabel")
        form.addWidget(key_label)

        key_row = QHBoxLayout()
        key_row.setSpacing(6)
        self.key_edit = QLineEdit(self.cfg.get("api_key", ""))
        self.key_edit.setEchoMode(QLineEdit.Password)
        self.key_edit.setPlaceholderText("sk-...")
        self.key_edit.setClearButtonEnabled(True)
        key_row.addWidget(self.key_edit, 1)
        self.eye_btn = QPushButton("显示")
        self.eye_btn.setObjectName("eye")
        self.eye_btn.setFixedWidth(52)
        self.eye_btn.clicked.connect(self._toggle_key_visibility)
        key_row.addWidget(self.eye_btn)
        form.addLayout(key_row)

        get_key = QLabel(
            '<a href="https://platform.deepseek.com/api_keys" '
            f'style="color:{GREEN}; text-decoration:none;">'
            "打开 DeepSeek 平台获取 API Key →</a>"
        )
        get_key.setOpenExternalLinks(False)
        get_key.setTextInteractionFlags(Qt.TextBrowserInteraction)
        get_key.linkActivated.connect(
            lambda url: QDesktopServices.openUrl(QUrl(url))
        )
        get_key.setObjectName("hint")
        form.addWidget(get_key)

        form.addSpacing(5)
        model_label = QLabel("模型")
        model_label.setObjectName("fieldLabel")
        form.addWidget(model_label)

        self.model_edit = QComboBox()
        self.model_edit.setEditable(True)
        self.model_edit.addItems(["deepseek-flash", "deepseek-v4-pro", "deepseek-chat"])
        self.model_edit.setCurrentText(self.cfg.get("model", MODEL_ID))
        self.model_edit.setToolTip("deepseek-flash 对应 DeepSeek V4.1 Flash")
        form.addWidget(self.model_edit)

        model_hint = QLabel("推荐 deepseek-flash（DeepSeek V4.1 Flash）")
        model_hint.setObjectName("hint")
        form.addWidget(model_hint)

        form.addSpacing(5)
        endpoint_label = QLabel("接口地址")
        endpoint_label.setObjectName("fieldLabel")
        form.addWidget(endpoint_label)

        self.endpoint_edit = QLineEdit(self.cfg.get("base_url", DEFAULT_ENDPOINT))
        self.endpoint_edit.setPlaceholderText(DEFAULT_ENDPOINT)
        form.addWidget(self.endpoint_edit)

        endpoint_hint = QLabel("默认使用 DeepSeek 官方 OpenAI 兼容接口，一般无需修改。")
        endpoint_hint.setObjectName("hint")
        form.addWidget(endpoint_hint)

        root.addWidget(card)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setMinimumHeight(24)
        self.status.setObjectName("hint")
        root.addWidget(self.status)

        footer = QHBoxLayout()
        self.config_hint = QLabel(f"Key 只保存在本机：{config_path()}")
        self.config_hint.setObjectName("hint")
        self.config_hint.setWordWrap(True)
        footer.addWidget(self.config_hint, 1)

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setObjectName("secondary")
        self.cancel_btn.clicked.connect(self.reject)
        footer.addWidget(self.cancel_btn)

        self.connect_btn = QPushButton("连接并保存")
        self.connect_btn.setObjectName("primary")
        self.connect_btn.setDefault(True)
        self.connect_btn.clicked.connect(self._test_and_save)
        footer.addWidget(self.connect_btn)
        root.addLayout(footer)

        self.key_edit.returnPressed.connect(self._test_and_save)

    def _toggle_key_visibility(self) -> None:
        if self.key_edit.echoMode() == QLineEdit.Password:
            self.key_edit.setEchoMode(QLineEdit.Normal)
            self.eye_btn.setText("隐藏")
        else:
            self.key_edit.setEchoMode(QLineEdit.Password)
            self.eye_btn.setText("显示")

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        for widget in (self.key_edit, self.model_edit, self.endpoint_edit,
                       self.eye_btn, self.connect_btn):
            widget.setEnabled(not busy)
        self.cancel_btn.setEnabled(not busy)
        self.connect_btn.setText("正在连接…" if busy else "连接并保存")

    def _show_status(self, text: str, color: str = MUTED) -> None:
        self.status.setStyleSheet(f"color: {color}; font-size: 12px;")
        self.status.setText(text)

    def _test_and_save(self) -> None:
        if self._busy:
            return
        key = self.key_edit.text().strip()
        model = self.model_edit.currentText().strip()
        if not key:
            self._show_status("请先填写 DeepSeek API Key。", DANGER)
            self.key_edit.setFocus()
            return
        if not model:
            self._show_status("请填写模型名称。", DANGER)
            return
        try:
            endpoint = normalize_endpoint(self.endpoint_edit.text())
        except ValueError as exc:
            self._show_status(str(exc), DANGER)
            return

        pending = dict(self.cfg)
        pending.update({
            "api_key": key,
            "model": model,
            "base_url": endpoint,
        })
        self._pending_cfg = pending
        self._set_busy(True)
        self._show_status("正在测试连接，请稍候…", GREEN)

        thread = ValidateThread(pending)
        self._thread = thread
        thread.ok.connect(self._on_connected)
        thread.failed.connect(self._on_failed)
        thread.finished.connect(self._on_thread_finished)
        thread.start()

    def _on_connected(self, model: str) -> None:
        if not self._pending_cfg:
            return
        save_config(self._pending_cfg)
        self.result_cfg = dict(self._pending_cfg)
        self.cfg = dict(self._pending_cfg)
        self._show_status(f"连接成功，当前模型：{model}", GREEN)
        QTimer.singleShot(420, self.accept)

    def _on_failed(self, message: str) -> None:
        self._show_status(message, DANGER)
        self._set_busy(False)

    def _on_thread_finished(self) -> None:
        thread = self._thread
        self._thread = None
        if thread is not None:
            thread.deleteLater()

    def closeEvent(self, event) -> None:
        if self._busy:
            self._show_status("正在验证连接，请稍候…", DANGER)
            event.ignore()
            return
        super().closeEvent(event)

    def shutdown(self) -> None:
        if self._thread is not None and self._thread.isRunning():
            self._thread.cancel()
            self._thread.wait(1200)
