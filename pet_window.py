import time
from PySide6.QtWidgets import QWidget, QMenu, QApplication, QLabel
from PySide6.QtGui import QPainter
from PySide6.QtCore import Qt, QTimer, QPoint
from animation import Animator
from bubble import Bubble
from harness_dialog import HarnessDialog
from admin_dialog import AdminDialog
from runtime_state import runtime


# ================= 悬浮的 deep 小标签 =================
class FloatIcon(QLabel):
    def __init__(self, on_click_callback):
        super().__init__()
        self.on_click = on_click_callback
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAlignment(Qt.AlignCenter)
        self.setText("deep")
        self.setStyleSheet("""
            QLabel {
                background: #F4FBFF;
                color: #183A55;
                border: 2px solid #7FB9D9;
                border-radius: 12px;
                padding: 4px 10px;
                font-size: 16px;
                font-weight: bold;
            }
        """)
        self.setFixedSize(78, 42)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.hide()
            self.on_click()


# ================= 桌宠主窗口 =================
class PetWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("肥鱼")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(100, 100)

        self.animator = Animator()
        self.animator.changed.connect(self.update)
        self.bubble = Bubble()
        self.harness = None
        self.admin = None
        self.float_icon = FloatIcon(self._wake_up)
        runtime.log("APP", "桌宠启动")

        self.drag_offset = None
        self.press_time = 0.0
        self.press_pos = QPoint()
        self.dragging = False
        self.last_mouse = 0.0
        self.last_key = 0.0

        self.short_press_count = 0
        self.last_short_press = 0.0
        self.press_window = 1.5
        self.trigger_count = 5

        self.state_timer = QTimer(self)
        self.state_timer.timeout.connect(self._update_state)
        self.state_timer.start(100)

        self._place_default()
        QTimer.singleShot(0, self._place_default)

    def _place_default(self):
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        margin = 56
        x = area.right() - self.width() - margin
        y = area.bottom() - self.height() - margin
        self.move(max(area.left(), x), max(area.top(), y))

    def _wake_up(self):
        runtime.log("UI", "从 deep 唤醒桌宠")
        self.show()
        self.raise_()
        self.activateWindow()

    def on_mouse_moved(self):
        self.last_mouse = time.time()
        runtime.bump_mouse()

    def on_key_pressed(self):
        self.last_key = time.time()
        runtime.bump_key()

    def _update_state(self):
        now = time.time()
        if self.dragging:
            self.animator.set_state("drag")
        elif now - self.last_key < 0.5:
            self.animator.set_state("key")
        elif now - self.last_mouse < 0.3:
            self.animator.set_state("mouse")
        else:
            self.animator.set_state("idle")
        self.update()

    def paintEvent(self, e):
        painter = QPainter(self)
        self.animator.paint(painter, self.rect())

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.press_time = time.time()
            self.press_pos = e.globalPosition().toPoint()
            self.drag_offset = self.press_pos - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self.drag_offset and (e.buttons() & Qt.LeftButton):
            cur = e.globalPosition().toPoint()
            if (cur - self.press_pos).manhattanLength() > 5:
                self.dragging = True
                self.move(cur - self.drag_offset)

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.LeftButton:
            return
        dt = time.time() - self.press_time
        moved = (e.globalPosition().toPoint() - self.press_pos).manhattanLength() > 5

        if self.dragging:
            self.dragging = False
        elif dt < 0.25 and not moved:
            self._handle_short_press()
        self.drag_offset = None

    def _handle_short_press(self):
        now = time.time()
        if now - self.last_short_press < self.press_window:
            self.short_press_count += 1
        else:
            self.short_press_count = 1
        self.last_short_press = now

        if self.short_press_count >= self.trigger_count:
            self.short_press_count = 0
            self._trigger_five()
        else:
            self._show_bubble("deep")

    def _trigger_five(self):
        self._show_bubble("deep")

    def _show_bubble(self, text):
        top_center = self.mapToGlobal(QPoint(self.width() // 2, 0))
        self.bubble.show_text(text, top_center)

    def contextMenuEvent(self, e):
        menu = QMenu(self)
        act_harness = menu.addAction("Harness 对话")
        act_admin = menu.addAction("管理后台")
        menu.addSeparator()
        act_hide = menu.addAction("隐藏")
        act_close = menu.addAction("关闭")

        act = menu.exec(e.globalPos())

        if act == act_harness:
            self._open_harness()
        elif act == act_admin:
            self._open_admin()
        elif act == act_hide:
            self.hide()
            runtime.log("UI", "桌宠已隐藏，显示 deep 悬浮标签")
            self.float_icon.move(self.x(), self.y())
            self.float_icon.show()
        elif act == act_close:
            if self.harness is not None:
                self.harness.shutdown()
            QApplication.quit()

    def _open_admin(self):
        runtime.log("UI", "打开管理后台")
        if self.admin is None:
            self.admin = AdminDialog()
        self.admin.show()
        self.admin.raise_()
        self.admin.activateWindow()

    def _open_harness(self):
        if self.harness is None:
            self.harness = HarnessDialog(pet=self)
        if self.harness.ensure_api_key():
            self.harness.show()
            self.harness.raise_()
            self.harness.activateWindow()

