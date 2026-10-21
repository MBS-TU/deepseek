"""Local admin console: persona, runtime status/events and model reasoning."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QFont, QIcon, QPixmap, QTextCursor
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QMessageBox, QPlainTextEdit, QPushButton, QTabWidget, QVBoxLayout,
    QWidget,
)

from api_client import MODEL_ID, SYSTEM_PROMPT
from api_settings import ApiSettingsDialog
from config_util import load_config, save_config
from paths import APP_VERSION, asset_path, config_path
from runtime_state import ReasoningTurn, runtime
from theme import (
    BORDER, CARD, DANGER, FONT_FAMILY, GREEN, GREEN_HOVER, INK, LEAF,
    MUTED, PAPER, PINE,
)

ADMIN_QSS = f"""
QDialog {{ background: {PAPER}; color: {INK}; font-family: "{FONT_FAMILY}"; }}
QFrame#adminHeader {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 {PINE}, stop:1 {GREEN});
    border: none;
}}
QLabel#adminTitle {{ color: white; font-size: 20px; font-weight: 700; }}
QLabel#adminSub {{ color: #D2ECFB; font-size: 10.5px; }}
QLabel#adminBadge {{
    color: #E2F4FF; background: rgba(255,255,255,24);
    border: 1px solid rgba(255,255,255,55);
    border-radius: 9px; padding: 5px 9px; font-size: 10px;
}}
QLabel#sectionTitle {{ color: {PINE}; font-size: 15px; font-weight: 700; }}
QLabel#hint {{ color: {MUTED}; font-size: 10.5px; }}
QLabel#statTitle {{ color: {MUTED}; font-size: 10px; }}
QLabel#statValue {{ color: {INK}; font-size: 12px; font-weight: 600; }}
QFrame#statCard {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 11px;
}}
QFrame#panel {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 14px;
}}
QTabWidget::pane {{
    border: 1px solid {BORDER};
    border-radius: 12px;
    background: {CARD};
    top: -1px;
}}
QTabBar::tab {{
    background: transparent;
    color: {MUTED};
    padding: 9px 20px;
    margin-right: 4px;
    border-bottom: 2px solid transparent;
    font-size: 12px;
    font-weight: 600;
}}
QTabBar::tab:selected {{ color: {PINE}; border-bottom: 2px solid {GREEN}; }}
QTabBar::tab:hover {{ color: {GREEN}; }}
QPlainTextEdit, QTextEdit {{
    background: #F8FDFF;
    color: {INK};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 8px;
    selection-background-color: {LEAF};
    font-size: 12px;
}}
QPlainTextEdit:focus, QTextEdit:focus {{ border: 1px solid {GREEN}; }}
QPlainTextEdit#console {{
    background: #162A39;
    color: #D9EDF8;
    border: 1px solid #2E4B61;
    font-family: "Consolas", "Cascadia Mono", monospace;
    font-size: 11px;
}}
QComboBox {{
    background: #F8FDFF;
    color: {INK};
    border: 1px solid {BORDER};
    border-radius: 9px;
    padding: 7px 10px;
    font-size: 12px;
}}
QComboBox::drop-down {{ border: none; width: 22px; }}
QPushButton {{
    border: 1px solid {BORDER};
    border-radius: 9px;
    background: {CARD};
    color: {PINE};
    padding: 8px 14px;
    font-size: 12px;
    font-weight: 600;
}}
QPushButton:hover {{ background: {LEAF}; }}
QPushButton#primary {{ background: {GREEN}; color: white; border-color: {GREEN}; }}
QPushButton#primary:hover {{ background: {GREEN_HOVER}; }}
QPushButton:disabled {{ color: #9AAEBD; background: #EDF5FA; }}
QLabel#pathLabel {{ color: {MUTED}; font-size: 9.5px; }}
QScrollBar:vertical {{ background: transparent; width: 9px; margin: 4px 2px; }}
QScrollBar::handle:vertical {{ background: #B7D1E2; border-radius: 4px; min-height: 26px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
"""

STATUS_NAMES = {
    "idle": "空闲",
    "thinking": "正在思考",
    "receiving": "正在回复",
    "error": "上次连接出错",
}


class AdminDialog(QDialog):
    def __init__(self):
        super().__init__(None)
        self.setWindowTitle("肥鱼 · 管理后台")
        self.setWindowIcon(QIcon(str(asset_path("icon.ico"))))
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.setMinimumSize(700, 580)
        self.resize(760, 650)
        self.setStyleSheet(ADMIN_QSS)

        self.cfg = load_config()
        self._placed = False
        self._loading_persona = False
        self._selected_turn = -1

        self._build_ui()
        self._load_persona()
        self._populate_events()
        self._rebuild_turns(select_latest=True)

        runtime.event_added.connect(self._append_event)
        runtime.turns_changed.connect(self._on_turns_changed)
        runtime.reasoning_updated.connect(self._on_reasoning_updated)
        runtime.status_changed.connect(self._refresh_status)

        self._status_timer = QTimer(self)
        self._status_timer.setInterval(1000)
        self._status_timer.timeout.connect(self._refresh_status)
        self._status_timer.start()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QFrame()
        header.setObjectName("adminHeader")
        header.setFixedHeight(82)
        h = QHBoxLayout(header)
        h.setContentsMargins(22, 13, 20, 13)
        h.setSpacing(12)

        avatar = QLabel()
        pix = QPixmap(str(asset_path("icon.png")))
        if not pix.isNull():
            avatar.setPixmap(pix.scaled(46, 46, Qt.KeepAspectRatio,
                                        Qt.SmoothTransformation))
        avatar.setFixedSize(46, 46)
        h.addWidget(avatar)

        titles = QVBoxLayout()
        titles.setSpacing(0)
        title = QLabel("管理后台")
        title.setObjectName("adminTitle")
        sub = QLabel("人设 · 运行状态 · 思考过程（仅本机）")
        sub.setObjectName("adminSub")
        titles.addWidget(title)
        titles.addWidget(sub)
        h.addLayout(titles)
        h.addStretch(1)

        badge = QLabel(f"v{APP_VERSION} · LOCAL")
        badge.setObjectName("adminBadge")
        h.addWidget(badge)
        root.addWidget(header)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        wrap = QWidget()
        wl = QVBoxLayout(wrap)
        wl.setContentsMargins(16, 12, 16, 14)
        wl.addWidget(self.tabs)
        root.addWidget(wrap, 1)

        self.tabs.addTab(self._build_persona_tab(), "人设")
        self.tabs.addTab(self._build_backend_tab(), "后台")
        self.tabs.addTab(self._build_reasoning_tab(), "思考过程")

    def _build_persona_tab(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(9)

        title = QLabel("肥鱼的人设")
        title.setObjectName("sectionTitle")
        lay.addWidget(title)

        hint = QLabel(
            "这里的内容会作为 system prompt 发给模型。可以改角色、称呼、说话方式和边界；"
            "保存后从下一轮对话开始生效。"
        )
        hint.setWordWrap(True)
        hint.setObjectName("hint")
        lay.addWidget(hint)

        self.persona_edit = QPlainTextEdit()
        self.persona_edit.setPlaceholderText("例如：你是……")
        self.persona_edit.setMinimumHeight(260)
        font = QFont(FONT_FAMILY)
        font.setPointSize(10)
        self.persona_edit.setFont(font)
        self.persona_edit.textChanged.connect(self._update_persona_count)
        lay.addWidget(self.persona_edit, 1)

        row = QHBoxLayout()
        self.persona_count = QLabel("")
        self.persona_count.setObjectName("hint")
        row.addWidget(self.persona_count)
        row.addStretch(1)

        reset = QPushButton("恢复默认文本")
        reset.clicked.connect(self._reset_persona)
        row.addWidget(reset)

        save = QPushButton("保存人设")
        save.setObjectName("primary")
        save.clicked.connect(self._save_persona)
        row.addWidget(save)
        lay.addLayout(row)

        self.persona_status = QLabel("")
        self.persona_status.setObjectName("hint")
        lay.addWidget(self.persona_status)

        note = QLabel(
            "人设保存在本地 config.json（已被 .gitignore 排除），不会进入仓库。"
        )
        note.setObjectName("hint")
        lay.addWidget(note)
        return page

    def _build_backend_tab(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(10)

        title = QLabel("运行状态")
        title.setObjectName("sectionTitle")
        lay.addWidget(title)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        self.stat_values: dict[str, QLabel] = {}
        specs = [
            ("api", "API 状态"), ("model", "模型"), ("chat", "当前对话"),
            ("input", "输入活动"), ("persona", "人设长度"), ("version", "程序版本"),
        ]
        for index, (key, label) in enumerate(specs):
            card = QFrame()
            card.setObjectName("statCard")
            cl = QVBoxLayout(card)
            cl.setContentsMargins(11, 8, 11, 8)
            cl.setSpacing(2)
            t = QLabel(label)
            t.setObjectName("statTitle")
            v = QLabel("—")
            v.setObjectName("statValue")
            v.setTextInteractionFlags(Qt.TextSelectableByMouse)
            cl.addWidget(t)
            cl.addWidget(v)
            self.stat_values[key] = v
            grid.addWidget(card, index // 3, index % 3)
        lay.addLayout(grid)

        path_row = QHBoxLayout()
        path_row.setSpacing(8)
        self.path_label = QLabel("")
        self.path_label.setObjectName("pathLabel")
        self.path_label.setWordWrap(True)
        self.path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        path_row.addWidget(self.path_label, 1)

        refresh = QPushButton("刷新")
        refresh.clicked.connect(self._refresh_status)
        path_row.addWidget(refresh)

        api_btn = QPushButton("修改 API 设置")
        api_btn.clicked.connect(self._open_api_settings)
        path_row.addWidget(api_btn)

        folder_btn = QPushButton("打开配置目录")
        folder_btn.clicked.connect(self._open_config_folder)
        path_row.addWidget(folder_btn)
        lay.addLayout(path_row)

        console_title = QHBoxLayout()
        ct = QLabel("后台事件（本次运行）")
        ct.setObjectName("sectionTitle")
        console_title.addWidget(ct)
        console_title.addStretch(1)
        clear = QPushButton("清空显示")
        clear.clicked.connect(self._clear_console)
        console_title.addWidget(clear)
        lay.addLayout(console_title)

        self.console = QPlainTextEdit()
        self.console.setObjectName("console")
        self.console.setReadOnly(True)
        self.console.setMaximumBlockCount(500)
        self.console.setPlaceholderText("还没有事件。")
        lay.addWidget(self.console, 1)

        self.listening_label = QLabel(
            "键鼠监听只统计活动次数，不记录按键内容；思考内容仅保存在内存。"
        )
        self.listening_label.setObjectName("hint")
        self.listening_label.setWordWrap(True)
        lay.addWidget(self.listening_label)
        return page

    def _build_reasoning_tab(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(9)

        title_row = QHBoxLayout()
        title = QLabel("模型思考过程")
        title.setObjectName("sectionTitle")
        title_row.addWidget(title)
        title_row.addStretch(1)
        self.reasoning_status = QLabel("暂无记录")
        self.reasoning_status.setObjectName("hint")
        title_row.addWidget(self.reasoning_status)
        lay.addLayout(title_row)

        hint = QLabel(
            "显示 DeepSeek 返回的 reasoning_content。它是模型生成的推理内容，"
            "可能不完整或出错；只在本次运行的内存里，不写入配置文件或日志。"
        )
        hint.setWordWrap(True)
        hint.setObjectName("hint")
        lay.addWidget(hint)

        selector_row = QHBoxLayout()
        self.turn_combo = QComboBox()
        self.turn_combo.setMinimumWidth(420)
        self.turn_combo.currentIndexChanged.connect(self._show_selected_turn)
        selector_row.addWidget(self.turn_combo, 1)

        copy_btn = QPushButton("复制")
        copy_btn.clicked.connect(self._copy_reasoning)
        selector_row.addWidget(copy_btn)

        clear_btn = QPushButton("清空记录")
        clear_btn.clicked.connect(self._clear_reasoning)
        selector_row.addWidget(clear_btn)
        lay.addLayout(selector_row)

        self.reasoning_view = QPlainTextEdit()
        self.reasoning_view.setReadOnly(True)
        self.reasoning_view.setPlaceholderText("模型开始回答后，思考过程会出现在这里。")
        font = QFont("Consolas")
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setPointSize(10)
        self.reasoning_view.setFont(font)
        lay.addWidget(self.reasoning_view, 1)

        self.reasoning_note = QLabel("")
        self.reasoning_note.setObjectName("hint")
        self.reasoning_note.setWordWrap(True)
        lay.addWidget(self.reasoning_note)
        return page

    # --------------------------------------------------------------- persona
    def _load_persona(self) -> None:
        self._loading_persona = True
        custom = (self.cfg.get("persona") or "").strip()
        self.persona_edit.setPlainText(custom or SYSTEM_PROMPT)
        self._loading_persona = False
        self._update_persona_count()

    def _update_persona_count(self) -> None:
        count = len(self.persona_edit.toPlainText())
        self.persona_count.setText(f"{count} 字")
        if self._loading_persona:
            return
        self.persona_status.setText("有未保存的修改。" if self._is_persona_dirty()
                                    else "")
        self.persona_status.setStyleSheet(f"color: {MUTED}; font-size: 10.5px;")

    def _is_persona_dirty(self) -> bool:
        saved = (self.cfg.get("persona") or "").strip() or SYSTEM_PROMPT.strip()
        return self.persona_edit.toPlainText().strip() != saved

    def _reset_persona(self) -> None:
        self.persona_edit.setPlainText(SYSTEM_PROMPT)
        self.persona_status.setText("已恢复默认文本，点“保存人设”后生效。")
        self.persona_status.setStyleSheet(f"color: {MUTED}; font-size: 10.5px;")

    def _save_persona(self) -> None:
        text = self.persona_edit.toPlainText().strip()
        if not text:
            self.persona_status.setText("人设不能为空。")
            self.persona_status.setStyleSheet(f"color: {DANGER}; font-size: 10.5px;")
            return
        stored = "" if text == SYSTEM_PROMPT.strip() else text
        self.cfg = load_config()
        self.cfg["persona"] = stored
        save_config(self.cfg)
        runtime.log("PERSONA", f"人设已保存 · {len(text)} 字")
        self.persona_status.setText("已保存，下一轮对话生效。")
        self.persona_status.setStyleSheet(f"color: {GREEN}; font-size: 10.5px;")
        self._refresh_status()

    # --------------------------------------------------------------- backend
    def _populate_events(self) -> None:
        for event in runtime.events:
            self._append_event(*event)

    def _append_event(self, stamp: str, level: str, message: str) -> None:
        self.console.appendPlainText(f"[{stamp}] {level:<7} {message}")
        bar = self.console.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _clear_console(self) -> None:
        self.console.clear()

    def _refresh_status(self) -> None:
        self.cfg = load_config()
        key_ok = bool((self.cfg.get("api_key") or "").strip())
        self._set_stat("api", "已配置" if key_ok else "未配置",
                       GREEN if key_ok else DANGER)
        self._set_stat("model", str(self.cfg.get("model") or MODEL_ID))
        self._set_stat("chat", STATUS_NAMES.get(runtime.chat_state, runtime.chat_state))
        self._set_stat("input",
                       f"鼠标 {runtime.mouse_events} / 键盘 {runtime.key_events}")
        persona_len = len((self.cfg.get("persona") or "").strip() or SYSTEM_PROMPT)
        self._set_stat("persona", f"{persona_len} 字")
        self._set_stat("version", f"v{APP_VERSION}")

        endpoint = str(self.cfg.get("base_url") or "")
        # Never display a URL userinfo / query string that could contain a key.
        try:
            parts = urlsplit(endpoint)
            host = parts.netloc.rsplit("@", 1)[-1]
            endpoint = urlunsplit((parts.scheme, host, parts.path, "", ""))
        except Exception:
            endpoint = "<invalid endpoint>"
        if len(endpoint) > 78:
            endpoint = endpoint[:75] + "…"
        self.path_label.setText(
            f"配置：{config_path()}\n接口：{endpoint}"
        )
        self.path_label.setToolTip(str(config_path()))

    def _set_stat(self, key: str, value: str, color: str = INK) -> None:
        label = self.stat_values.get(key)
        if label is not None:
            label.setText(value)
            label.setStyleSheet(f"color: {color}; font-size: 12px; font-weight: 600;")

    def _open_config_folder(self) -> None:
        folder = Path(config_path()).parent
        folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def _open_api_settings(self) -> None:
        dlg = ApiSettingsDialog(load_config(), parent=self)
        accepted = dlg.exec()
        dlg.shutdown()
        if accepted:
            self.cfg = load_config()
            self._refresh_status()
            runtime.log("API", "API 设置已更新")

    # -------------------------------------------------------------- reasoning
    def _on_turns_changed(self) -> None:
        self._rebuild_turns(select_latest=True)

    def _rebuild_turns(self, select_latest: bool = False) -> None:
        previous = self._selected_turn
        self.turn_combo.blockSignals(True)
        self.turn_combo.clear()
        for index, turn in enumerate(runtime.turns):
            self.turn_combo.addItem(self._turn_label(turn), index)
        count = len(runtime.turns)
        if count == 0:
            self.turn_combo.setEnabled(False)
            self._selected_turn = -1
            self.reasoning_view.clear()
            self.reasoning_status.setText("暂无记录")
            self.reasoning_status.setStyleSheet(
                f"color: {MUTED}; font-size: 10.5px;")
            self.reasoning_note.setText(
                "还没有对话记录。发一条消息后，如果模型返回 reasoning_content，"
                "这里会实时出现。"
            )
        else:
            self.turn_combo.setEnabled(True)
            if select_latest or previous < 0 or previous >= count:
                selected = count - 1
            else:
                selected = previous
                self.turn_combo.setCurrentIndex(selected)
            self._selected_turn = selected
            self.turn_combo.setCurrentIndex(selected)
            self._show_selected_turn()
        self.turn_combo.blockSignals(False)

    @staticmethod
    def _turn_label(turn: ReasoningTurn) -> str:
        prompt = turn.prompt or "（空消息）"
        if len(prompt) > 42:
            prompt = prompt[:42] + "…"
        return f"{turn.started} · {prompt}"

    def _show_selected_turn(self) -> None:
        index = self.turn_combo.currentData()
        if index is None or index < 0 or index >= len(runtime.turns):
            self._selected_turn = -1
            return
        self._selected_turn = int(index)
        turn = runtime.turns[self._selected_turn]
        if turn.reasoning:
            self.reasoning_view.setPlainText(turn.reasoning)
            cursor = self.reasoning_view.textCursor()
            cursor.movePosition(QTextCursor.End)
            self.reasoning_view.setTextCursor(cursor)
        elif turn.status in ("thinking", "receiving"):
            self.reasoning_view.setPlainText("模型正在思考，思考内容会实时显示在这里…")
        elif turn.status == "no_reasoning":
            self.reasoning_view.setPlainText(
                "本轮没有收到 reasoning_content。\n\n"
                "可能原因：接口未返回思考内容、模型未开启思考模式，或使用了不支持的代理。"
            )
        elif turn.status == "failed":
            self.reasoning_view.setPlainText(
                "本轮在思考过程中出错。\n\n" + (turn.note or "")
            )
        elif turn.status == "cancelled":
            self.reasoning_view.setPlainText("本轮已停止，没有更多思考内容。")
        else:
            self.reasoning_view.clear()

        color = DANGER if turn.status == "failed" else (
            GREEN if turn.status == "thinking" else MUTED)
        self.reasoning_status.setText(turn.status_text)
        self.reasoning_status.setStyleSheet(
            f"color: {color}; font-size: 10.5px; font-weight: 600;")
        self.reasoning_note.setText(
            f"{turn.started} · {turn.model} · "
            f"思考 {len(turn.reasoning)} 字 · 回答 {turn.answer_chars} 字"
        )

    def _on_reasoning_updated(self) -> None:
        if not runtime.turns:
            self._rebuild_turns()
            return
        if self._selected_turn == len(runtime.turns) - 1:
            self._show_selected_turn()
        elif self._selected_turn < 0:
            self._rebuild_turns(select_latest=True)

    def _copy_reasoning(self) -> None:
        text = self.reasoning_view.toPlainText().strip()
        if text:
            QApplication.clipboard().setText(text)
            self.reasoning_status.setText("已复制")
            self.reasoning_status.setStyleSheet(f"color: {GREEN}; font-size: 10.5px;")

    def _clear_reasoning(self) -> None:
        if runtime.chat_state in ("thinking", "receiving"):
            self.reasoning_status.setText("对话进行中，结束后再清空")
            self.reasoning_status.setStyleSheet(f"color: {DANGER}; font-size: 10.5px;")
            return
        if QMessageBox.question(
            self, "清空思考记录", "清空当前进程里的所有思考记录？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        ) != QMessageBox.Yes:
            return
        runtime.clear_turns()
        self.reasoning_note.setText("已清空本次运行的思考记录。")

    # ---------------------------------------------------------------- window
    def _place_once(self) -> None:
        if self._placed:
            return
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        width = min(760, max(680, area.width() - 100))
        height = min(650, max(560, area.height() - 80))
        self.resize(width, height)
        self.move(area.left() + (area.width() - width) // 2,
                  area.top() + (area.height() - height) // 2)
        self._placed = True

    def showEvent(self, event) -> None:
        self._place_once()
        self._refresh_status()
        super().showEvent(event)
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event) -> None:
        event.accept()
