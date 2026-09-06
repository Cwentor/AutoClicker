"""鼠标连点器 - 基于 PySide6 的液态毛玻璃风格自动点击工具。

毛玻璃实现：抓取窗口背后的屏幕区域，高斯模糊后绘制为窗口背景，
拖动结束后自动刷新（Qt 分层窗口无法直接使用 DWM 背景模糊）。
"""

import ctypes
import sys
import threading
import time

import pyautogui
import keyboard
from PySide6.QtCore import QRect, QRectF, Qt, QTimer, Signal, QRegularExpression
from PySide6.QtGui import (
    QColor, QFont, QImage, QPainter, QPixmap, QRegularExpressionValidator,
)
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QFrame, QGraphicsBlurEffect, QGraphicsScene,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QPushButton, QVBoxLayout,
    QWidget,
)

APP_VERSION = "v1.3"

# 关闭 pyautogui 每次调用后的默认暂停（0.1s），保证点击间隔与设置值一致
pyautogui.PAUSE = 0

MIN_INTERVAL = 0.01

ACCENT = "#5b8cff"
BLUR_RADIUS = 26
FROST_TINT = QColor(248, 250, 255, 92)

DOT_COLORS = {
    "idle": "#9a9aa8",
    "running": "#30d158",
    "pulse": "#8df2a8",
    "paused": "#ff9f0a",
    "stopped": "#9a9aa8",
    "error": "#ff453a",
}

STYLE_SHEET = """
QMainWindow, QWidget#root {
    background: transparent;
}
QLabel {
    color: #1c1c2e;
    background: transparent;
}
QFrame#card {
    background: rgba(255, 255, 255, 0.52);
    border: 1px solid rgba(255, 255, 255, 0.75);
    border-radius: 20px;
}
QLabel#title {
    font-size: 26px;
    font-weight: 700;
}
QLabel#subtitle, QLabel#section, QLabel#hint {
    color: rgba(28, 28, 46, 0.52);
}
QLabel#subtitle { font-size: 12px; }
QLabel#section { font-size: 13px; font-weight: 600; }
QLabel#hint { font-size: 11px; }
QLabel#statusText {
    font-size: 17px;
    font-weight: 600;
}
QLineEdit#field {
    background: rgba(255, 255, 255, 0.62);
    border: 1px solid rgba(255, 255, 255, 0.90);
    border-radius: 10px;
    padding: 6px 10px;
    font-size: 15px;
    color: #1c1c2e;
    selection-background-color: %(accent)s;
}
QLineEdit#field:focus {
    border: 1px solid %(accent)s;
}
QPushButton#chip {
    background: rgba(255, 255, 255, 0.42);
    border: 1px solid rgba(28, 28, 46, 0.10);
    border-radius: 13px;
    padding: 5px 16px;
    font-size: 12px;
    color: #1c1c2e;
}
QPushButton#chip:hover {
    background: rgba(255, 255, 255, 0.80);
}
QPushButton#segBtn {
    background: transparent;
    border: none;
    border-radius: 16px;
    padding: 7px 26px;
    font-size: 13px;
    color: rgba(28, 28, 46, 0.55);
}
QPushButton#segBtn:checked {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #6a5cff, stop:1 #4da3ff);
    color: #ffffff;
    font-weight: 600;
}
QPushButton#action {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #6a5cff, stop:1 #4da3ff);
    border: none;
    border-radius: 24px;
    padding: 14px 40px;
    font-size: 15px;
    font-weight: 700;
    color: #ffffff;
}
QPushButton#action:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #7d70ff, stop:1 #63b2ff);
}
QPushButton#action:pressed {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #5a4de0, stop:1 #3f8fe0);
}
QPushButton#titleBtn, QPushButton#closeBtn {
    background: transparent;
    border: none;
    border-radius: 8px;
    color: #3a3a50;
    font-size: 13px;
    padding: 4px 12px;
}
QPushButton#titleBtn:hover, QPushButton#closeBtn:hover {
    background: rgba(28, 28, 46, 0.08);
}
QPushButton#closeBtn:hover {
    background: #e81123;
    color: #ffffff;
}
""" % {"accent": ACCENT}


def _dwm_set(hwnd, attr, value):
    v = ctypes.c_int(value)
    return ctypes.windll.dwmapi.DwmSetWindowAttribute(
        ctypes.c_void_p(hwnd), attr, ctypes.byref(v), 4
    )


def round_corners(hwnd):
    try:
        _dwm_set(hwnd, 33, 2)  # DWMWCP_ROUND 窗口圆角
    except Exception:
        pass


def blurred_pixmap(pix, radius):
    """对 QPixmap 做高斯模糊。"""
    scene = QGraphicsScene()
    item = scene.addPixmap(pix)
    effect = QGraphicsBlurEffect()
    effect.setBlurRadius(radius)
    effect.setBlurHints(QGraphicsBlurEffect.BlurHint.QualityHint)
    item.setGraphicsEffect(effect)
    result = QImage(pix.size(), QImage.Format.Format_ARGB32_Premultiplied)
    result.fill(0)
    painter = QPainter(result)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    scene.render(painter, QRectF(result.rect()), QRectF(pix.rect()))
    painter.end()
    return QPixmap.fromImage(result)


class GlassRoot(QWidget):
    """中央控件：把模糊后的桌面背景绘制在最底层。"""

    def __init__(self):
        super().__init__(objectName="root")
        self._bg = None

    def set_background(self, pixmap):
        self._bg = pixmap
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        if self._bg is not None and not self._bg.isNull():
            painter.drawPixmap(self.rect(), self._bg)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(FROST_TINT)
        painter.drawRect(self.rect())


class TitleBar(QFrame):
    """自绘标题栏：拖动移动窗口、最小化与关闭按钮。"""

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.setFixedHeight(44)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 0, 10, 0)

        app_title = QLabel("鼠标连点器")
        f = app_title.font()
        f.setPointSize(10)
        f.setBold(True)
        app_title.setFont(f)
        layout.addWidget(app_title)
        layout.addStretch()

        min_btn = QPushButton("—")
        min_btn.setObjectName("titleBtn")
        min_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        min_btn.clicked.connect(window.showMinimized)
        layout.addWidget(min_btn)

        close_btn = QPushButton("✕")
        close_btn.setObjectName("closeBtn")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(window.close)
        layout.addWidget(close_btn)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.window._drag_pos = event.globalPosition().toPoint() - self.window.pos()

    def mouseMoveEvent(self, event):
        if self.window._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.window.move(event.globalPosition().toPoint() - self.window._drag_pos)

    def mouseReleaseEvent(self, event):
        self.window._drag_pos = None
        self.window.schedule_glass_refresh()


class AutoClicker(QMainWindow):
    # 热键回调运行在 keyboard 库线程，经信号调度回 GUI 主线程
    state_changed = Signal(str, str, str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"鼠标连点器 {APP_VERSION}")
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(760, 640)
        self._drag_pos = None
        self._glass_ready = False

        self.click_interval = "0.1"
        self.mouse_button = "left"
        self.running = False
        self.stop_program = False
        self.click_thread = None
        self._pulse = False

        self.state_changed.connect(self.apply_state)
        self._build_ui()

        self.glass_timer = QTimer(self)
        self.glass_timer.setSingleShot(True)
        self.glass_timer.setInterval(120)
        self.glass_timer.timeout.connect(self.refresh_glass)

        keyboard.add_hotkey('ctrl+alt', self.toggle_running)
        keyboard.add_hotkey('alt+q', self.stop)

        self.pulse_timer = QTimer(self)
        self.pulse_timer.timeout.connect(self._animate)
        self.pulse_timer.start(400)

    # ---------- 界面构建 ----------

    def _build_ui(self):
        root = GlassRoot()
        self.root_widget = root
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(TitleBar(self))

        body = QVBoxLayout()
        body.setContentsMargins(32, 4, 32, 18)
        body.setSpacing(16)
        outer.addLayout(body)

        # 标题
        header = QVBoxLayout()
        header.setSpacing(2)
        title = QLabel("鼠标连点器", objectName="title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle = QLabel(f"自动点击 · 全局快捷键控制 · {APP_VERSION}", objectName="subtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addWidget(title)
        header.addWidget(subtitle)
        body.addLayout(header)

        # 运行状态
        status_card = QFrame(objectName="card")
        status_layout = QVBoxLayout(status_card)
        status_layout.setContentsMargins(20, 18, 20, 18)
        status_layout.setSpacing(10)
        dot_row = QHBoxLayout()
        dot_row.addStretch()
        self.dot = QLabel()
        self.dot.setFixedSize(14, 14)
        self.dot.setStyleSheet(f"background: {DOT_COLORS['idle']}; border-radius: 7px;")
        dot_row.addWidget(self.dot)
        dot_row.addStretch()
        self.status_text = QLabel("待机", objectName="statusText")
        self.status_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_layout.addLayout(dot_row)
        status_layout.addWidget(self.status_text)
        body.addWidget(status_card)

        # 点击间隔
        interval_card = QFrame(objectName="card")
        interval_layout = QVBoxLayout(interval_card)
        interval_layout.setContentsMargins(20, 16, 20, 16)
        interval_layout.setSpacing(12)
        interval_layout.addWidget(QLabel("点击间隔", objectName="section"))

        entry_row = QHBoxLayout()
        entry_row.addStretch()
        self.entry = QLineEdit(self.click_interval, objectName="field")
        self.entry.setFixedWidth(120)
        self.entry.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.entry.setValidator(QRegularExpressionValidator(
            QRegularExpression(r"\d*\.?\d*")))
        self.entry.textChanged.connect(self._on_interval_changed)
        entry_row.addWidget(self.entry)
        entry_row.addWidget(QLabel("秒"))
        entry_row.addStretch()
        interval_layout.addLayout(entry_row)

        preset_row = QHBoxLayout()
        preset_row.setSpacing(10)
        preset_row.addWidget(QLabel("预设", objectName="hint"))
        for t in ("0.05", "0.1", "0.5", "1"):
            chip = QPushButton(t, objectName="chip")
            chip.setCursor(Qt.CursorShape.PointingHandCursor)
            chip.clicked.connect(lambda _=False, v=t: self.entry.setText(v))
            preset_row.addWidget(chip)
        preset_row.addStretch()
        preset_row.addWidget(QLabel(f"最小 {MIN_INTERVAL} 秒", objectName="hint"))
        interval_layout.addLayout(preset_row)
        body.addWidget(interval_card)

        # 点击按钮
        button_card = QFrame(objectName="card")
        button_layout = QHBoxLayout(button_card)
        button_layout.setContentsMargins(20, 14, 20, 14)
        button_layout.addWidget(QLabel("点击按钮", objectName="section"))
        button_layout.addStretch()

        seg_group = QButtonGroup(self)
        seg_group.setExclusive(True)
        self.seg_buttons = {}
        for value, label in (("left", "左键"), ("right", "右键")):
            btn = QPushButton(label, objectName="segBtn")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setChecked(value == self.mouse_button)
            btn.toggled.connect(lambda on, v=value: on and self._set_mouse_button(v))
            seg_group.addButton(btn)
            self.seg_buttons[value] = btn
            button_layout.addWidget(btn)
        body.addWidget(button_card)

        # 主操作按钮
        action_row = QHBoxLayout()
        action_row.addStretch()
        self.action_btn = QPushButton("开始连点  (CTRL+ALT)", objectName="action")
        self.action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.action_btn.clicked.connect(self.toggle_running)
        action_row.addWidget(self.action_btn)
        action_row.addStretch()
        body.addLayout(action_row)

        body.addStretch()

        # 底部提示
        footer = QLabel("CTRL + ALT   开始 / 暂停          ALT + Q   停止程序",
                        objectName="hint")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body.addWidget(footer)
        fail_hint = QLabel("紧急停止：将鼠标快速移至屏幕左上角", objectName="hint")
        fail_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body.addWidget(fail_hint)

    # ---------- 毛玻璃背景 ----------

    def schedule_glass_refresh(self):
        self.glass_timer.start()

    def refresh_glass(self):
        """抓取窗口背后的屏幕区域，模糊后作为窗口背景。"""
        if not self.isVisible():
            return
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            return
        geo = self.frameGeometry()
        self.setWindowOpacity(0.0)
        try:
            full = screen.grabWindow(0)
        finally:
            self.setWindowOpacity(1.0)
        dpr = full.devicePixelRatio() or 1.0
        rect = QRect(round(geo.x() * dpr), round(geo.y() * dpr),
                     round(geo.width() * dpr), round(geo.height() * dpr))
        rect = rect.intersected(full.rect())
        if rect.isEmpty():
            return
        crop = full.copy(rect)
        self.root_widget.set_background(blurred_pixmap(crop, BLUR_RADIUS))

    def showEvent(self, event):
        super().showEvent(event)
        if not self._glass_ready:
            self._glass_ready = True
            round_corners(int(self.winId()))
            QTimer.singleShot(80, self.refresh_glass)

    def moveEvent(self, event):
        super().moveEvent(event)
        self.schedule_glass_refresh()

    # ---------- 状态与交互 ----------

    def _on_interval_changed(self, text):
        self.click_interval = text

    def _set_mouse_button(self, value):
        self.mouse_button = value

    def get_interval(self):
        try:
            value = float(self.click_interval)
        except ValueError:
            value = MIN_INTERVAL
        return max(value, MIN_INTERVAL)

    def apply_state(self, text, dot_color, button_text):
        self.status_text.setText(text)
        self.dot.setStyleSheet(f"background: {dot_color}; border-radius: 7px;")
        self.action_btn.setText(button_text)

    def set_state(self, key, text, button_text):
        self.state_changed.emit(text, DOT_COLORS[key], button_text)

    def toggle_running(self):
        self.running = not self.running
        if self.running:
            self.set_state("running", "连点中", "暂停  (CTRL+ALT)")
            if not self.click_thread or not self.click_thread.is_alive():
                self.stop_program = False
                self.click_thread = threading.Thread(target=self.click_loop)
                self.click_thread.daemon = True
                self.click_thread.start()
        else:
            self.set_state("paused", "已暂停", "继续连点  (CTRL+ALT)")

    def click_loop(self):
        while not self.stop_program:
            if self.running:
                try:
                    pyautogui.click(button=self.mouse_button)
                    time.sleep(self.get_interval())
                except pyautogui.FailSafeException:
                    # 鼠标移至屏幕左上角触发防失控保护，自动停止连点
                    self.running = False
                    self.set_state("error", "已触发防失控保护", "开始连点  (CTRL+ALT)")
                except Exception:
                    self.running = False
                    self.set_state("error", "出错已停止", "开始连点  (CTRL+ALT)")
            else:
                time.sleep(0.1)

    def stop(self):
        self.running = False
        self.stop_program = True
        self.set_state("stopped", "已停止", "开始连点  (CTRL+ALT)")
        if self.click_thread and self.click_thread.is_alive():
            self.click_thread.join(timeout=1)

    def _animate(self):
        """连点时状态指示灯呼吸闪烁。"""
        if self.running:
            self._pulse = not self._pulse
            color = DOT_COLORS["pulse"] if self._pulse else DOT_COLORS["running"]
            self.dot.setStyleSheet(f"background: {color}; border-radius: 7px;")
        else:
            self._pulse = False

    def closeEvent(self, event):
        self.stop()
        keyboard.unhook_all_hotkeys()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setFont(QFont("Microsoft YaHei", 10))
    window = AutoClicker()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
