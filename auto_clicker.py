import pyautogui
import time
import keyboard
import tkinter as tk
from tkinter import ttk
import threading

class AutoClickerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("鼠标连点器")
        
        # 设置窗口尺寸（增大显示比例）
        window_width = 680
        window_height = 540
        
        # 计算窗口居中位置
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        
        # 设置窗口位置和大小
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
        self.root.resizable(False, False)
        
        # 设置窗口图标和样式
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        # 配置ttk组件样式
        self.style.configure("TButton", font=("微软雅黑", 11))
        self.style.configure("TLabel", font=("微软雅黑", 11))
        self.style.configure("TEntry", font=("微软雅黑", 11))
        self.style.configure("TRadiobutton", font=("微软雅黑", 11))
        # 配置LabelFrame的标题居中对齐
        self.style.configure("TLabelframe.Label", anchor="center", font=("微软雅黑", 11, "bold"))
        
        # 变量
        self.click_interval = tk.DoubleVar(value=0.1)
        self.button_var = tk.StringVar(value='left')
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
        
        # 创建点击间隔的容器，用于居中对齐
        interval_container = ttk.Frame(interval_frame)
        interval_container.pack(fill=tk.BOTH, expand=True)
        
        # 使用grid布局实现水平居中
        interval_container.grid_columnconfigure(0, weight=1)
        interval_container.grid_columnconfigure(3, weight=1)
        
        interval_entry = ttk.Entry(interval_container, textvariable=self.click_interval, width=12)
        interval_entry.grid(row=0, column=1, padx=(0, 15))
        
        interval_label = ttk.Label(interval_container, text="秒")
        interval_label.grid(row=0, column=2)
        
        # 点击按钮选择
        button_frame = ttk.LabelFrame(main_frame, text="点击按钮", padding="15")
        button_frame.pack(fill=tk.X, pady=(0, 20))
        
        # 创建单选按钮的容器，用于居中对齐
        radio_container = ttk.Frame(button_frame)
        radio_container.pack(fill=tk.BOTH, expand=True)
        
        # 使用grid布局实现水平居中
        radio_container.grid_columnconfigure(0, weight=1)
        radio_container.grid_columnconfigure(3, weight=1)
        
        left_radio = ttk.Radiobutton(radio_container, text="左键", variable=self.button_var, value='left')
        left_radio.grid(row=0, column=1, padx=(0, 30))
        
        right_radio = ttk.Radiobutton(radio_container, text="右键", variable=self.button_var, value='right')
        right_radio.grid(row=0, column=2)
        
        # 提示信息 - 重新定位至点击按钮选择模块下方
        hint_frame = ttk.LabelFrame(main_frame, text="快捷键提示", padding="15")
        hint_frame.pack(fill=tk.X, pady=(0, 20))
        
        # 创建快捷键提示的容器，用于居中对齐
        hint_container = ttk.Frame(hint_frame)
        hint_container.pack(fill=tk.BOTH, expand=True)
        
        # 使用grid布局实现水平居中
        hint_container.grid_columnconfigure(0, weight=1)
        hint_container.grid_columnconfigure(5, weight=1)
        
        start_pause_hint = ttk.Label(hint_container, text="CTRL+ALT", foreground="#0066cc")
        start_pause_hint.grid(row=0, column=1, padx=(0, 15))
        # 设置粗体字体
        start_pause_hint.configure(font=("微软雅黑", 11, "bold"))
        
        start_pause_text = ttk.Label(hint_container, text="开始/暂停连点", foreground="#333333")
        start_pause_text.grid(row=0, column=2, padx=(0, 30))
        
        stop_hint = ttk.Label(hint_container, text="ALT+Q", foreground="#0066cc")
        stop_hint.grid(row=0, column=3, padx=(0, 15))
        # 设置粗体字体
        stop_hint.configure(font=("微软雅黑", 11, "bold"))
        
        stop_text = ttk.Label(hint_container, text="停止程序", foreground="#333333")
        stop_text.grid(row=0, column=4)
    
    def toggle_running(self):
        self.running = not self.running
        if self.running:
            if not self.click_thread or not self.click_thread.is_alive():
                self.click_thread = threading.Thread(target=self.click_loop)
                self.click_thread.daemon = True
                self.click_thread.start()
    
    def click_loop(self):
        while not self.stop_program:
            if self.running:
                try:
                    pyautogui.click(button=self.button_var.get())
                    time.sleep(self.click_interval.get())
                except Exception as e:
                    self.running = False
            else:
                time.sleep(0.1)
    
    def stop(self):
        self.running = False
        self.stop_program = True
        
        # 等待线程结束
        if self.click_thread and self.click_thread.is_alive():
            self.click_thread.join(timeout=1)
    
    def on_closing(self):
        self.stop()
        keyboard.unhook_all_hotkeys()
        self.root.destroy()

def main():
    root = tk.Tk()
    app = AutoClickerGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
