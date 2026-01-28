import tkinter as tk
import threading
import time
import ctypes
import sys

# 尝试导入 pyautogui，如果没有安装也能运行 API 模式
try:
    import pyautogui

    HAS_PYAUTOGUI = True
    pyautogui.FAILSAFE = False
except ImportError:
    HAS_PYAUTOGUI = False


class PowerfulAntiLockApp:
    def __init__(self, root):
        self.root = root
        self.root.title("防锁屏工具 (增强版)")
        self.root.geometry("350x220")
        self.root.resizable(False, False)

        # 状态标志
        self.is_running = False

        # Windows API 常量定义
        self.ES_CONTINUOUS = 0x80000000
        self.ES_SYSTEM_REQUIRED = 0x00000001
        self.ES_DISPLAY_REQUIRED = 0x00000002

        # 界面布局
        self.status_label = tk.Label(root, text="状态: 🔴 已停止", fg="#d9534f", font=("微软雅黑", 16, "bold"))
        self.status_label.pack(pady=25)

        self.info_label = tk.Label(root, text="模式: Windows API + 虚拟按键", fg="#666666", font=("Arial", 9))
        self.info_label.pack(pady=0)

        btn_frame = tk.Frame(root)
        btn_frame.pack(pady=15)

        self.btn_start = tk.Button(btn_frame, text="开启防锁屏", command=self.start_program,
                                   width=12, height=2, bg="#5cb85c", fg="white", font=("bold"))
        self.btn_start.pack(side=tk.LEFT, padx=10)

        self.btn_stop = tk.Button(btn_frame, text="停止", command=self.stop_program,
                                  width=12, height=2, state=tk.DISABLED, bg="#f0f0f0")
        self.btn_stop.pack(side=tk.LEFT, padx=10)

    def set_keep_awake(self, enable=True):
        """调用 Windows 底层 API 设置防睡眠状态"""
        try:
            if enable:
                # 强制系统和显示器处于工作状态
                ctypes.windll.kernel32.SetThreadExecutionState(
                    self.ES_CONTINUOUS | self.ES_SYSTEM_REQUIRED | self.ES_DISPLAY_REQUIRED
                )
            else:
                # 恢复正常状态
                ctypes.windll.kernel32.SetThreadExecutionState(self.ES_CONTINUOUS)
        except Exception as e:
            print(f"API 调用失败: {e}")

    def start_program(self):
        if not self.is_running:
            self.is_running = True
            self.status_label.config(text="状态: 🟢 运行中...", fg="#5cb85c")
            self.btn_start.config(state=tk.DISABLED, bg="#f0f0f0", fg="black")
            self.btn_stop.config(state=tk.NORMAL, bg="#d9534f", fg="white")

            # 立即调用一次 API
            self.set_keep_awake(True)

            # 开启循环线程作为双重保险
            self.thread = threading.Thread(target=self.keep_awake_loop)
            self.thread.daemon = True
            self.thread.start()

    def stop_program(self):
        if self.is_running:
            self.is_running = False
            self.status_label.config(text="状态: 🔴 已停止", fg="#d9534f")
            self.btn_start.config(state=tk.NORMAL, bg="#5cb85c", fg="white")
            self.btn_stop.config(state=tk.DISABLED, bg="#f0f0f0", fg="black")

            # 恢复系统正常休眠策略
            self.set_keep_awake(False)

    def keep_awake_loop(self):
        """双重保险循环：定期刷新 API 状态并按键"""
        while self.is_running:
            try:
                # 1. 再次刷新 Windows API 状态 (防止被系统策略重置)
                self.set_keep_awake(True)

                # 2. 模拟物理按键 (F15 是功能键，通常不干扰打字)
                # 如果没有装 pyautogui，这步会跳过
                if HAS_PYAUTOGUI:
                    pyautogui.press('f15')
                    # 或者微动一下鼠标作为三重保险（极小幅度）
                    # pyautogui.moveRel(0, 0)

                # 每 50 秒执行一次
                for _ in range(50):
                    if not self.is_running: break
                    time.sleep(1)

            except Exception as e:
                print(f"Loop error: {e}")
                break


if __name__ == "__main__":
    root = tk.Tk()
    app = PowerfulAntiLockApp(root)


    def on_closing():
        app.stop_program()
        root.destroy()


    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()