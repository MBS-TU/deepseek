"""In-memory runtime information shared by the pet, Harness and admin window.

Reasoning text is deliberately kept only in memory: it is never written to the
log file, the config file, or the repository.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime

from PySide6.QtCore import QObject, Signal


@dataclass
class ReasoningTurn:
    started: str
    prompt: str
    model: str
    reasoning: str = ""
    answer_chars: int = 0
    status: str = "thinking"  # thinking / receiving / done / cancelled / failed / no_reasoning
    note: str = ""

    @property
    def status_text(self) -> str:
        return {
            "thinking": "正在思考…",
            "receiving": "正在回答…",
            "done": "已完成",
            "cancelled": "已停止",
            "failed": "出错",
            "no_reasoning": "未返回思考过程",
        }.get(self.status, self.status)


class RuntimeState(QObject):
    event_added = Signal(str, str, str)  # time, level, message
    turns_changed = Signal()
    reasoning_updated = Signal()
    status_changed = Signal()

    MAX_EVENTS = 300
    MAX_TURNS = 20

    def __init__(self) -> None:
        super().__init__()
        self.events: deque[tuple[str, str, str]] = deque(maxlen=self.MAX_EVENTS)
        self.turns: list[ReasoningTurn] = []
        self.current_turn: ReasoningTurn | None = None
        self.chat_state = "idle"
        self.mouse_events = 0
        self.key_events = 0
        self.listening = False

    # --------------------------------------------------------------- events
    def log(self, level: str, message: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        self.events.append((stamp, level, message))
        self.event_added.emit(stamp, level, message)

    def format_event(self, event: tuple[str, str, str]) -> str:
        stamp, level, message = event
        return f"[{stamp}] {level:<7} {message}"

    # ------------------------------------------------------------- thinking
    def begin_turn(self, prompt: str, model: str) -> ReasoningTurn:
        preview = " ".join((prompt or "").split())
        if len(preview) > 52:
            preview = preview[:52] + "…"
        turn = ReasoningTurn(
            started=datetime.now().strftime("%H:%M:%S"),
            prompt=preview or "（空消息）",
            model=model,
        )
        self.turns.append(turn)
        if len(self.turns) > self.MAX_TURNS:
            del self.turns[0]
        self.current_turn = turn
        self.chat_state = "thinking"
        self.log("CHAT", f"开始请求 · {model}")
        self.turns_changed.emit()
        self.reasoning_updated.emit()
        self.status_changed.emit()
        return turn

    def append_reasoning(self, text: str) -> None:
        if not text or self.current_turn is None:
            return
        first = not self.current_turn.reasoning
        self.current_turn.reasoning += text
        self.current_turn.status = "thinking"
        if first:
            self.log("THINK", "开始接收思考过程")
        self.reasoning_updated.emit()

    def mark_receiving(self, answer_chars: int = 0) -> None:
        turn = self.current_turn
        if turn is None:
            return
        if turn.status == "thinking":
            self.log("CHAT", "思考结束，开始接收正文")
            self.chat_state = "receiving"
            self.status_changed.emit()
        turn.status = "receiving"
        turn.answer_chars = max(turn.answer_chars, answer_chars)

    def finish_turn(self, answer_chars: int = 0) -> None:
        turn = self.current_turn
        if turn is None:
            self.chat_state = "idle"
            self.status_changed.emit()
            return
        turn.answer_chars = max(turn.answer_chars, answer_chars)
        if turn.reasoning:
            turn.status = "done"
            self.log("CHAT", f"回复完成 · 思考 {len(turn.reasoning)} 字 / 回答 {answer_chars} 字")
        else:
            turn.status = "no_reasoning"
            self.log("CHAT", f"回复完成 · 未返回思考过程（回答 {answer_chars} 字）")
        self.chat_state = "idle"
        self.turns_changed.emit()
        self.reasoning_updated.emit()
        self.status_changed.emit()

    def cancel_turn(self) -> None:
        turn = self.current_turn
        if turn is not None:
            turn.status = "cancelled"
            self.log("CHAT", "对话已停止")
        self.chat_state = "idle"
        self.turns_changed.emit()
        self.reasoning_updated.emit()
        self.status_changed.emit()

    def fail_turn(self, message: str) -> None:
        turn = self.current_turn
        if turn is not None:
            turn.status = "failed"
            turn.note = message or "未知错误"
        self.chat_state = "error"
        self.log("ERROR", (message or "对话出错").replace("\n", " ")[:180])
        self.turns_changed.emit()
        self.reasoning_updated.emit()
        self.status_changed.emit()

    def clear_turns(self) -> None:
        self.turns.clear()
        self.current_turn = None
        self.chat_state = "idle"
        self.turns_changed.emit()
        self.reasoning_updated.emit()
        self.status_changed.emit()

    # --------------------------------------------------------------- counts
    def bump_mouse(self) -> None:
        self.mouse_events += 1

    def bump_key(self) -> None:
        self.key_events += 1


runtime = RuntimeState()
