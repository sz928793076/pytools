import sys
import os
import time
import json
import pyautogui
import pyperclip
import ctypes
import pygetwindow as gw
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                               QPushButton, QLabel, QComboBox, QLineEdit, QScrollArea,
                               QFileDialog, QTextEdit, QMessageBox, QFrame, QListWidget)
from PySide6.QtCore import Qt, QThread, Signal

# --- DPI 修复 ---
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except:
        pass

CONFIG_DIR = "configs"
if not os.path.exists(CONFIG_DIR): os.makedirs(CONFIG_DIR)


# --------------------------
# 核心引擎 (决策增强版)
# --------------------------
class RPAEngine:
    def __init__(self):
        self.is_running = False
        self.stop_requested = False

    def stop(self):
        self.stop_requested = True
        self.is_running = False

    def _sleep(self, sec):
        for _ in range(int(sec * 10)):
            if self.stop_requested: return
            time.sleep(0.1)

    def _find_and_click(self, img, region, confidence=0.7, timeout=1):
        """快速找图并点击，找不到立即返回"""
        if not img or not os.path.exists(img): return False
        try:
            loc = pyautogui.locateCenterOnScreen(img, confidence=confidence, region=region)
            if loc:
                pyautogui.click(loc.x, loc.y, duration=0.2)
                return True
        except:
            pass
        return False

    def run_tasks(self, tasks, loop_forever=False, target_window_title=None, callback_msg=None):
        self.is_running = True
        self.stop_requested = False

        try:
            while not self.stop_requested:
                region = None
                # 窗口锁定
                if target_window_title and target_window_title != "全屏模式":
                    wins = gw.getWindowsWithTitle(target_window_title)
                    if wins:
                        win = wins[0]
                        if win.isMinimized: win.restore()
                        win.activate()
                        region = (int(win.left), int(win.top), int(win.width), int(win.height))

                for idx, task in enumerate(tasks):
                    if self.stop_requested: break

                    t_type = task.get("type")
                    t_val = task.get("value")
                    t_delay = float(task.get("delay", 0.5))

                    if callback_msg: callback_msg(f"执行: {CMD_TYPES_REV.get(t_type)}")

                    # --- 基础指令 ---
                    if t_type == 1.0:  # 单击 (带超时，找不到就跳过)
                        self._find_and_click(t_val, region, timeout=2)

                    elif t_type == 4.0:  # 输入
                        pyperclip.copy(str(t_val))
                        pyautogui.hotkey('ctrl', 'v')

                    elif t_type == 7.0:  # 按键
                        pyautogui.press(str(t_val).lower())

                    elif t_type == 11.0:  # 角色移动 (格式: w,3)
                        try:
                            key, duration = str(t_val).split(',')
                            pyautogui.keyDown(key.strip())
                            self._sleep(float(duration))
                            pyautogui.keyUp(key.strip())
                        except:
                            pass

                    # --- 核心：决策循环 (用于处理随机卡片和战斗) ---
                    elif t_type == 10.0:
                        if callback_msg: callback_msg("进入[智能决策模式]...")
                        # 这是一个内部循环，直到检测到副本结束
                        while not self.stop_requested:
                            # 1. 检测战斗中 (如果看到右下角图标，就挂机)
                            if self._find_and_click(task.get("battle_img"), region):
                                if callback_msg: callback_msg("战斗中...")
                                self._sleep(2)
                                continue

                            # 2. 检测到选卡 (点击第一张卡，并点确认)
                            if self._find_and_click(task.get("card_img"), region):
                                if callback_msg: callback_msg("检测到卡片，准备选择...")
                                self._sleep(1)
                                self._find_and_click(task.get("confirm_img"), region)
                                continue

                            # 3. 检测到交互 (按F)
                            if self._find_and_click(task.get("f_img"), region):
                                pyautogui.press('f')
                                self._sleep(1)
                                continue

                            # 4. 前进逻辑 (如果没有检测到任何UI，就往前走)
                            pyautogui.keyDown('w')
                            self._sleep(1)
                            pyautogui.keyUp('w')

                            # 5. 退出判定 (如果看到副本结算，退出循环)
                            if self._find_and_click(task.get("exit_img"), region):
                                if callback_msg: callback_msg("副本结束")
                                break

                            self._sleep(0.5)

                    self._sleep(t_delay)

                if not loop_forever: break
        finally:
            self.is_running = False
            if callback_msg: callback_msg("运行结束")


# --------------------------
# GUI 逻辑 (简化适配)
# --------------------------
CMD_TYPES = {
    "左键单击": 1.0, "输入文本": 4.0, "系统按键": 7.0,
    "智能决策模式": 10.0, "角色移动(键,秒)": 11.0, "等待(秒)": 5.0
}
CMD_TYPES_REV = {v: k for k, v in CMD_TYPES.items()}


class TaskRow(QFrame):
    def __init__(self, parent_layout, delete_callback):
        super().__init__()
        self.setFrameShape(QFrame.StyledPanel)
        layout = QHBoxLayout(self)
        self.type_combo = QComboBox();
        self.type_combo.addItems(list(CMD_TYPES.keys()))
        self.val_input = QLineEdit();
        self.val_input.setPlaceholderText("参数")
        self.delay_input = QLineEdit("0.5");
        self.delay_input.setFixedWidth(40)
        self.del_btn = QPushButton("×");
        self.del_btn.clicked.connect(lambda: delete_callback(self))

        layout.addWidget(self.type_combo)
        layout.addWidget(self.val_input)
        layout.addWidget(QLabel("间隔:"))
        layout.addWidget(self.delay_input)
        layout.addWidget(self.del_btn)
        parent_layout.insertWidget(parent_layout.count() - 1, self)

    def get_data(self):
        # 决策模式特殊处理
        if self.type_combo.currentText() == "智能决策模式":
            return {
                "type": 10.0,
                "battle_img": "images/in_battle.png",  # 需手动在images文件夹准备
                "card_img": "images/card_tag.png",
                "confirm_img": "images/confirm.png",
                "f_img": "images/f_interact.png",
                "exit_img": "images/exit.png",
                "delay": 0.5
            }
        return {"type": CMD_TYPES[self.type_combo.currentText()], "value": self.val_input.text(),
                "delay": self.delay_input.text()}

    def set_data(self, data):
        self.type_combo.setCurrentText(CMD_TYPES_REV.get(data.get('type'), "左键单击"))
        self.val_input.setText(str(data.get('value', "")))
        self.delay_input.setText(str(data.get('delay', 0.5)))


class RPAWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("崩坏星穹铁道-差分宇宙 RPA")
        self.resize(800, 600)
        self.engine = RPAEngine()
        self.rows = []

        widget = QWidget();
        self.setCentralWidget(widget)
        layout = QVBoxLayout(widget)

        # 控制栏
        ctrl = QHBoxLayout()
        self.win_combo = QComboBox()
        self.refresh_wins()
        ctrl.addWidget(QLabel("目标窗口:"))
        ctrl.addWidget(self.win_combo)

        add_btn = QPushButton("添加步骤");
        add_btn.clicked.connect(self.add_row)
        start_btn = QPushButton("启动");
        start_btn.clicked.connect(self.start)
        stop_btn = QPushButton("停止");
        stop_btn.clicked.connect(self.stop)
        ctrl.addWidget(add_btn);
        ctrl.addWidget(start_btn);
        ctrl.addWidget(stop_btn)
        layout.addLayout(ctrl)

        # 任务列表
        scroll = QScrollArea();
        scroll.setWidgetResizable(True)
        self.task_cont = QWidget();
        self.task_layout = QVBoxLayout(self.task_cont)
        self.task_layout.addStretch()
        scroll.setWidget(self.task_cont)
        layout.addWidget(scroll)

        self.log = QTextEdit();
        self.log.setMaximumHeight(100);
        layout.addWidget(self.log)
        self.add_row()

    def refresh_wins(self):
        self.win_combo.clear()
        self.win_combo.addItems(["全屏模式"] + [w.title for w in gw.getAllWindows() if w.title])

    def add_row(self, data=None):
        row = TaskRow(self.task_layout, self.delete_row)
        if data: row.set_data(data)
        self.rows.append(row)

    def delete_row(self, r):
        self.rows.remove(r);
        r.deleteLater()

    def start(self):
        tasks = [r.get_data() for r in self.rows]
        self.worker = WorkerThread(self.engine, tasks, self.win_combo.currentText())
        self.worker.log_signal.connect(self.log.append)
        self.worker.start()

    def stop(self): self.engine.stop()


class WorkerThread(QThread):
    log_signal = Signal(str)

    def __init__(self, engine, tasks, win):
        super().__init__()
        self.engine, self.tasks, self.win = engine, tasks, win

    def run(self):
        self.engine.run_tasks(self.tasks, False, self.win, lambda m: self.log_signal.emit(m))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = RPAWindow();
    win.show()
    sys.exit(app.exec())