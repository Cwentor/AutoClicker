"""鼠标连点器 - 一个简单易用的图形化自动点击工具。"""

import sys
import time
import threading
import tkinter as tk
from tkinter import ttk

import pyautogui
import keyboard

APP_VERSION = "v1.1"

# 关闭 pyautogui 每次调用后的默认暂停（0.1s），保证点击间隔与设置值一致
pyautogui.PAUSE = 0

MIN_INTERVAL = 0.01


class AutoClickerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title(f"鼠标连点器 {APP_VERSION}")

        # 设置窗口尺寸并居中显示
        window_width = 680
        window_height = 580
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
        self.root.resizable(False, False)

        # 配置ttk组件样式
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.style.configure("TButton", font=("微软雅黑", 11))
        self.style.configure("TLabel", font=("微软雅黑", 11))
        self.style.configure("TEntry", font=("微软雅黑", 11))
        self.style.configure("TRadiobutton", font=("微软雅黑", 11))
        self.style.configure("TLabelframe.Label", anchor="center", font=("微软雅黑", 11, "bold"))

        # 变量
        self.click_interval = tk.StringVar(value="0.1")
        self.button_var = tk.StringVar(value='left')
        self.status_var = tk.StringVar(value="状态：待机")
        self.running = False
        self.stop_program = False
        self.click_thread = None

        # 创建界面
        self.create_widgets()

        # 设置热键
        keyboard.add_hotkey('ctrl+alt', self.toggle_running)
        keyboard.add_hotkey('alt+q', self.stop)

        # 窗口关闭时的处理
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def create_widgets(self):
        # 主框架
        main_frame = ttk.Frame(self.root, padding="30")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 标题
        title_label = ttk.Label(main_frame, text="鼠标连点器", font=("微软雅黑", 20, "bold"))
        title_label.pack(pady=(0, 30))

        # 点击间隔设置
        interval_frame = ttk.LabelFrame(main_frame, text="点击间隔", padding="15")
        interval_frame.pack(fill=tk.X, pady=(0, 20))

        interval_container = ttk.Frame(interval_frame)
        interval_container.pack(fill=tk.BOTH, expand=True)
        interval_container.grid_columnconfigure(0, weight=1)
        interval_container.grid_columnconfigure(4, weight=1)

        # 仅允许输入合法的数字，避免非法输入导致点击线程报错
        vcmd = (self.root.register(self.validate_interval), '%P')
        interval_entry = ttk.Entry(
            interval_container, textvariable=self.click_interval,
            width=12, justify=tk.CENTER, validate='key', validatecommand=vcmd
        )
        interval_entry.grid(row=0, column=1, padx=(0, 15))

        interval_label = ttk.Label(interval_container, text="秒")
        interval_label.grid(row=0, column=2)

        hint_label = ttk.Label(
            interval_container, text=f"（最小 {MIN_INTERVAL} 秒）", foreground="#999999"
        )
        hint_label.grid(row=0, column=3, padx=(15, 0))

        # 点击按钮选择
        button_frame = ttk.LabelFrame(main_frame, text="点击按钮", padding="15")
        button_frame.pack(fill=tk.X, pady=(0, 20))

        radio_container = ttk.Frame(button_frame)
        radio_container.pack(fill=tk.BOTH, expand=True)
        radio_container.grid_columnconfigure(0, weight=1)
        radio_container.grid_columnconfigure(3, weight=1)

        left_radio = ttk.Radiobutton(radio_container, text="左键", variable=self.button_var, value='left')
        left_radio.grid(row=0, column=1, padx=(0, 30))

        right_radio = ttk.Radiobutton(radio_container, text="右键", variable=self.button_var, value='right')
        right_radio.grid(row=0, column=2)

        # 运行状态
        status_frame = ttk.LabelFrame(main_frame, text="运行状态", padding="15")
        status_frame.pack(fill=tk.X, pady=(0, 20))

        status_container = ttk.Frame(status_frame)
        status_container.pack(fill=tk.BOTH, expand=True)
        status_container.grid_columnconfigure(0, weight=1)
        status_container.grid_columnconfigure(2, weight=1)

        self.status_label = ttk.Label(status_container, textvariable=self.status_var, anchor=tk.CENTER)
        self.status_label.grid(row=0, column=1)

        # 提示信息
        hint_frame = ttk.LabelFrame(main_frame, text="快捷键提示", padding="15")
        hint_frame.pack(fill=tk.X, pady=(0, 20))

        hint_container = ttk.Frame(hint_frame)
        hint_container.pack(fill=tk.BOTH, expand=True)
        hint_container.grid_columnconfigure(0, weight=1)
        hint_container.grid_columnconfigure(5, weight=1)

        start_pause_hint = ttk.Label(hint_container, text="CTRL+ALT", foreground="#0066cc",
                                     font=("微软雅黑", 11, "bold"))
        start_pause_hint.grid(row=0, column=1, padx=(0, 15))

        start_pause_text = ttk.Label(hint_container, text="开始/暂停连点", foreground="#333333")
        start_pause_text.grid(row=0, column=2, padx=(0, 30))

        stop_hint = ttk.Label(hint_container, text="ALT+Q", foreground="#0066cc",
                              font=("微软雅黑", 11, "bold"))
        stop_hint.grid(row=0, column=3, padx=(0, 15))

        stop_text = ttk.Label(hint_container, text="停止程序", foreground="#333333")
        stop_text.grid(row=0, column=4)

    @staticmethod
    def validate_interval(new_value):
        """校验点击间隔输入：允许空串或合法的非负数字。"""
        if new_value == "":
            return True
        try:
            value = float(new_value)
        except ValueError:
            return False
        return value >= 0

    def get_interval(self):
        """读取点击间隔，非法或过小时回落到最小值。"""
        try:
            value = float(self.click_interval.get())
        except (ValueError, tk.TclError):
            value = MIN_INTERVAL
        return max(value, MIN_INTERVAL)

    def set_status(self, text, color):
        """更新状态栏；热键回调运行在非主线程，需经 root.after 调度回主线程。"""
        def update():
            self.status_var.set(text)
            self.status_label.configure(foreground=color)
        self.root.after(0, update)

    def toggle_running(self):
        self.running = not self.running
        if self.running:
            self.set_status("状态：连点中", "#008800")
            if not self.click_thread or not self.click_thread.is_alive():
                self.stop_program = False
                self.click_thread = threading.Thread(target=self.click_loop)
                self.click_thread.daemon = True
                self.click_thread.start()
        else:
            self.set_status("状态：已暂停", "#cc6600")

    def click_loop(self):
        while not self.stop_program:
            if self.running:
                try:
                    pyautogui.click(button=self.button_var.get())
                    time.sleep(self.get_interval())
                except pyautogui.FailSafeException:
                    # 鼠标移至屏幕左上角触发防失控保护，自动停止连点
                    self.running = False
                    self.set_status("状态：已触发防失控保护，已停止", "#cc0000")
                except Exception:
                    self.running = False
                    self.set_status("状态：出错已停止", "#cc0000")
            else:
                time.sleep(0.1)

    def stop(self):
        self.running = False
        self.stop_program = True
        self.set_status("状态：已停止", "#999999")

        if self.click_thread and self.click_thread.is_alive():
            self.click_thread.join(timeout=1)

    def on_closing(self):
        self.stop()
        keyboard.unhook_all_hotkeys()
        self.root.destroy()


def main():
    root = tk.Tk()
    AutoClickerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
