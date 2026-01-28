import sys
import os
import time
import json
import shutil
import pyautogui
import pyperclip
import traceback
import ctypes
import pygetwindow as gw
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                               QPushButton, QLabel, QComboBox, QLineEdit, QScrollArea,
                               QFileDialog, QTextEdit, QMessageBox, QFrame, QListWidget)
from PySide6.QtCore import Qt, QThread, Signal

# --------------------------
# Windows DPI 唤醒
# --------------------------
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except:
        pass

CONFIG_DIR = "configs"
if not os.path.exists(CONFIG_DIR):
    os.makedirs(CONFIG_DIR)


# --------------------------
# 核心引擎
# --------------------------
class RPAEngine:
    def __init__(self):
        self.is_running = False
        self.stop_requested = False

    def stop(self):
        self.stop_requested = True
        self.is_running = False

    def _interruptible_sleep(self, seconds):
        for _ in range(int(seconds * 10)):
            if self.stop_requested:
                return
            time.sleep(0.1)

    def _wait_and_click(self, clickTimes, lOrR, img, reTry, region, timeout=15):
        if not img or not os.path.exists(img):
            return False
        start_time = time.time()
        while not self.stop_requested:
            if timeout and (time.time() - start_time > timeout):
                return False
            try:
                location = pyautogui.locateCenterOnScreen(img, confidence=0.7, region=region)
                if location is not None:
                    pyautogui.click(location.x, location.y, clicks=clickTimes, interval=0.2, duration=0.2, button=lOrR)
                    if reTry > 1:
                        for _ in range(reTry - 1):
                            if self.stop_requested: break
                            pyautogui.click(location.x, location.y, clicks=1, interval=0.1, button=lOrR)
                    return True
            except Exception:
                pass
            time.sleep(0.5)
        return False

    def _wait_and_move(self, img, region, timeout=15):
        start_time = time.time()
        while not self.stop_requested:
            if timeout and (time.time() - start_time > timeout):
                return False
            try:
                location = pyautogui.locateCenterOnScreen(img, confidence=0.7, region=region)
                if location is not None:
                    pyautogui.moveTo(location.x, location.y, duration=0.2)
                    return True
            except Exception:
                pass
            time.sleep(0.5)
        return False

    def run_tasks(self, tasks, loop_forever=False, target_window_title=None, callback_msg=None):
        self.is_running = True
        self.stop_requested = False

        try:
            while not self.stop_requested:
                region = None
                if target_window_title and target_window_title != "全屏模式":
                    try:
                        wins = gw.getWindowsWithTitle(target_window_title)
                        if wins:
                            win = wins[0]
                            if win.isMinimized: win.restore()
                            win.activate()
                            time.sleep(1.0)
                            region = (int(win.left), int(win.top), int(win.width), int(win.height))
                            if callback_msg: callback_msg(f"锁定窗口区域: {region}")
                    except Exception as e:
                        if callback_msg: callback_msg(f"窗口锁定异常: {e}")

                for idx, task in enumerate(tasks):
                    if self.stop_requested: break
                    cmd_type = task.get("type")
                    cmd_value = task.get("value")
                    retry = task.get("retry", 1)
                    delay_after = float(task.get("delay", 0.5))
                    desc_text = task.get("desc", "")

                    type_name = CMD_TYPES_REV.get(cmd_type, '未知')
                    log_text = f"▶ 步骤 {idx + 1}: [{type_name}]"
                    if desc_text: log_text += f" - {desc_text}"
                    if callback_msg: callback_msg(log_text)

                    success = True
                    if cmd_type == 1.0:
                        success = self._wait_and_click(1, "left", cmd_value, retry, region)
                    elif cmd_type == 2.0:
                        success = self._wait_and_click(2, "left", cmd_value, retry, region)
                    elif cmd_type == 3.0:
                        success = self._wait_and_click(1, "right", cmd_value, retry, region)
                    elif cmd_type == 4.0:
                        pyperclip.copy(str(cmd_value))
                        pyautogui.hotkey('ctrl', 'v')
                    elif cmd_type == 5.0:
                        self._interruptible_sleep(float(cmd_value))
                    elif cmd_type == 6.0:
                        pyautogui.scroll(int(cmd_value))
                    elif cmd_type == 7.0:
                        keys = [k.strip() for k in str(cmd_value).lower().split('+')]
                        pyautogui.hotkey(*keys)
                    elif cmd_type == 8.0:
                        success = self._wait_and_move(cmd_value, region)
                    elif cmd_type == 9.0:
                        pyautogui.screenshot(cmd_value, region=region)

                    if not success and cmd_type in [1.0, 2.0, 3.0, 8.0]:
                        if callback_msg: callback_msg(f"  [!] 未匹配到图像")

                    if callback_msg and delay_after > 0:
                        self._interruptible_sleep(delay_after)

                if not loop_forever: break
                time.sleep(0.1)
        finally:
            self.is_running = False
            if callback_msg: callback_msg("任务运行结束")


# --------------------------
# GUI 组件
# --------------------------
CMD_TYPES = {"左键单击": 1.0, "左键双击": 2.0, "右键单击": 3.0, "输入文本": 4.0, "等待(秒)": 5.0, "滚轮滑动": 6.0,
             "系统按键": 7.0, "鼠标悬停": 8.0, "截图保存": 9.0}
CMD_TYPES_REV = {v: k for k, v in CMD_TYPES.items()}

# 【再次优化】列宽度定义：步骤说明拉大到 350
COL_WIDTHS = {
    "type": 100,
    "desc": 350,  # 极大增强描述列宽度
    "value": 250,
    "file": 35,
    "retry": 45,
    "delay": 45,
    "del": 35
}


class TaskRow(QFrame):
    def __init__(self, parent_layout, delete_callback):
        super().__init__()
        self.setFrameShape(QFrame.StyledPanel)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 2, 5, 2)
        layout.setSpacing(10)

        # 1. 指令类型
        self.type_combo = QComboBox()
        self.type_combo.addItems(list(CMD_TYPES.keys()))
        self.type_combo.setFixedWidth(COL_WIDTHS["type"])
        layout.addWidget(self.type_combo)

        # 2. 步骤说明 (宽度 350)
        self.desc_input = QLineEdit()
        self.desc_input.setPlaceholderText("在这里写下这一步要做什么，方便以后查看...")
        self.desc_input.setFixedWidth(COL_WIDTHS["desc"])
        layout.addWidget(self.desc_input)

        # 3. 参数/路径
        self.value_input = QLineEdit()
        self.value_input.setPlaceholderText("参数/路径/按键")
        layout.addWidget(self.value_input)

        # 4. 文件按钮
        self.file_btn = QPushButton("..")
        self.file_btn.setFixedWidth(COL_WIDTHS["file"])
        self.file_btn.clicked.connect(self.select_file)
        layout.addWidget(self.file_btn)

        # 5. 重试
        self.retry_input = QLineEdit("1")
        self.retry_input.setFixedWidth(COL_WIDTHS["retry"])
        self.retry_input.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.retry_input)

        # 6. 间隔
        self.delay_input = QLineEdit("0.5")
        self.delay_input.setFixedWidth(COL_WIDTHS["delay"])
        self.delay_input.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.delay_input)

        # 7. 删除
        self.del_btn = QPushButton("×")
        self.del_btn.setFixedWidth(COL_WIDTHS["del"])
        self.del_btn.setStyleSheet("color: red; font-weight: bold;")
        self.del_btn.clicked.connect(lambda: delete_callback(self))
        layout.addWidget(self.del_btn)

        parent_layout.insertWidget(parent_layout.count() - 1, self)

    def select_file(self):
        cmd_text = self.type_combo.currentText()
        if "截图" in cmd_text:
            path = QFileDialog.getExistingDirectory(self, "选择保存目录")
            if path: self.value_input.setText(path)
        elif any(x in cmd_text for x in ["单击", "双击", "悬停", "右键"]):
            path, _ = QFileDialog.getOpenFileName(self, "选择图片", "", "Images (*.png *.jpg *.bmp)")
            if path: self.value_input.setText(path)

    def get_data(self):
        try:
            retry = int(self.retry_input.text())
            delay = float(self.delay_input.text())
        except:
            retry, delay = 1, 0.5
        return {
            "type": CMD_TYPES[self.type_combo.currentText()],
            "desc": self.desc_input.text(),
            "value": self.value_input.text(),
            "retry": retry,
            "delay": delay
        }

    def set_data(self, data):
        self.type_combo.setCurrentText(CMD_TYPES_REV.get(data['type'], "左键单击"))
        self.desc_input.setText(str(data.get('desc', "")))
        self.value_input.setText(str(data.get('value', "")))
        self.retry_input.setText(str(data.get('retry', 1)))
        self.delay_input.setText(str(data.get('delay', 0.5)))


class WorkerThread(QThread):
    log_signal = Signal(str)
    finished_signal = Signal()

    def __init__(self, engine, tasks, loop, window_title):
        super().__init__()
        self.engine, self.tasks, self.loop, self.window_title = engine, tasks, loop, window_title

    def run(self):
        self.engine.run_tasks(self.tasks, self.loop, self.window_title, lambda m: self.log_signal.emit(m))
        self.finished_signal.emit()


class RPAWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RPA 自动化工具 ")
        self.resize(1400, 800)  # 增加默认宽度
        self.engine = RPAEngine()
        self.rows = []

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_h_layout = QHBoxLayout(central_widget)

        # --- 左侧面板 ---
        self.left_panel = QVBoxLayout()
        self.left_panel.addWidget(QLabel("<b>本地配置库:</b>"))
        self.config_list = QListWidget()
        self.config_list.setFixedWidth(200)
        self.config_list.itemDoubleClicked.connect(self.load_selected_config)
        self.left_panel.addWidget(self.config_list)

        btn_grid = QVBoxLayout()
        self.import_btn = QPushButton("📥 导入外部配置")
        self.import_btn.clicked.connect(self.import_config)
        self.import_btn.setStyleSheet("height: 35px; background-color: #2196F3; color: white; font-weight: bold;")

        sub_btn_layout = QHBoxLayout()
        self.refresh_btn = QPushButton("刷新列表")
        self.refresh_btn.clicked.connect(self.refresh_config_list)
        self.del_config_btn = QPushButton("删除配置")
        self.del_config_btn.clicked.connect(self.delete_selected_config)
        sub_btn_layout.addWidget(self.refresh_btn)
        sub_btn_layout.addWidget(self.del_config_btn)

        btn_grid.addWidget(self.import_btn)
        btn_grid.addLayout(sub_btn_layout)
        self.left_panel.addLayout(btn_grid)
        self.main_h_layout.addLayout(self.left_panel, 1)

        # --- 右侧面板 ---
        self.right_panel = QVBoxLayout()

        # 顶部工具栏
        top_bar = QHBoxLayout()
        self.window_combo = QComboBox()
        self.refresh_windows()
        top_bar.addWidget(QLabel("目标窗口:"))
        top_bar.addWidget(self.window_combo)

        self.win_refresh_btn = QPushButton("🔄")
        self.win_refresh_btn.setFixedWidth(30)
        self.win_refresh_btn.clicked.connect(self.refresh_windows)
        top_bar.addWidget(self.win_refresh_btn)
        top_bar.addStretch()

        self.add_btn = QPushButton("+ 新增步骤")
        self.add_btn.clicked.connect(lambda: self.add_row())
        top_bar.addWidget(self.add_btn)

        self.save_btn = QPushButton("💾 保存配置")
        self.save_btn.clicked.connect(self.save_config)
        top_bar.addWidget(self.save_btn)

        self.loop_combo = QComboBox()
        self.loop_combo.addItems(["执行一次", "循环执行"])
        top_bar.addWidget(self.loop_combo)

        self.start_btn = QPushButton("▶ 开始运行")
        self.start_btn.clicked.connect(self.start_task)
        self.start_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; width: 100px;")
        top_bar.addWidget(self.start_btn)

        self.stop_btn = QPushButton("⏹ 停止")
        self.stop_btn.clicked.connect(self.stop_task)
        self.stop_btn.setStyleSheet("background-color: #f44336; color: white; font-weight: bold;")
        top_bar.addWidget(self.stop_btn)
        self.right_panel.addLayout(top_bar)

        # --- 表头 ---
        header_frame = QFrame()
        header_frame.setStyleSheet("background-color: #eeeeee; font-weight: bold; border-radius: 4px;")
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(15, 8, 15, 8)
        header_layout.setSpacing(10)

        h_type = QLabel("指令类型");
        h_type.setFixedWidth(COL_WIDTHS["type"])
        h_desc = QLabel("步骤说明 (任务描述)");
        h_desc.setFixedWidth(COL_WIDTHS["desc"])
        h_val = QLabel("具体内容/路径")
        h_file = QLabel("..");
        h_file.setFixedWidth(COL_WIDTHS["file"])
        h_retry = QLabel("重试");
        h_retry.setFixedWidth(COL_WIDTHS["retry"]);
        h_retry.setAlignment(Qt.AlignCenter)
        h_delay = QLabel("间隔");
        h_delay.setFixedWidth(COL_WIDTHS["delay"]);
        h_delay.setAlignment(Qt.AlignCenter)
        h_del = QLabel("操作");
        h_del.setFixedWidth(COL_WIDTHS["del"])

        header_layout.addWidget(h_type)
        header_layout.addWidget(h_desc)
        header_layout.addWidget(h_val)
        header_layout.addWidget(h_file)
        header_layout.addWidget(h_retry)
        header_layout.addWidget(h_delay)
        header_layout.addWidget(h_del)
        self.right_panel.addWidget(header_frame)

        # 任务列表区
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        self.task_container = QWidget()
        self.task_layout = QVBoxLayout(self.task_container)
        self.task_layout.setContentsMargins(5, 5, 5, 5)
        self.task_layout.addStretch()
        scroll.setWidget(self.task_container)
        self.right_panel.addWidget(scroll)

        # 【调整】日志区高度压缩至 100
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setFixedHeight(100)  # 固定高度为100
        self.log_area.setStyleSheet(
            "background-color: #1e1e1e; color: #00ff00; font-family: Consolas; font-size: 11px; padding: 5px;")
        self.right_panel.addWidget(QLabel("<b>运行日志 (实时):</b>"))
        self.right_panel.addWidget(self.log_area)

        self.main_h_layout.addLayout(self.right_panel, 5)
        self.refresh_config_list()
        self.add_row()

    def refresh_windows(self):
        cur = self.window_combo.currentText()
        self.window_combo.clear()
        self.window_combo.addItem("全屏模式")
        titles = sorted(list(set([w.title for w in gw.getAllWindows() if w.title])))
        self.window_combo.addItems(titles)
        if cur in titles: self.window_combo.setCurrentText(cur)

    def refresh_config_list(self):
        self.config_list.clear()
        if not os.path.exists(CONFIG_DIR): os.makedirs(CONFIG_DIR)
        files = sorted([f for f in os.listdir(CONFIG_DIR) if f.endswith(".json")])
        self.config_list.addItems(files)

    def import_config(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择要导入的配置文件", "", "JSON Files (*.json)")
        if path:
            try:
                filename = os.path.basename(path)
                dest_path = os.path.join(CONFIG_DIR, filename)
                if os.path.exists(dest_path):
                    res = QMessageBox.question(self, "覆盖提示", f"配置 '{filename}' 已存在，是否覆盖？")
                    if res == QMessageBox.No: return

                shutil.copy(path, dest_path)
                self.refresh_config_list()
                self.log_area.append(f"✅ 成功导入: {filename}")
            except Exception as e:
                QMessageBox.critical(self, "导入失败", f"错误: {e}")

    def load_selected_config(self, item):
        path = os.path.join(CONFIG_DIR, item.text())
        try:
            with open(path, 'r', encoding='utf-8') as f:
                tasks = json.load(f)
            for r in self.rows: r.deleteLater()
            self.rows.clear()
            for t in tasks: self.add_row(t)
            self.log_area.append(f"📂 已加载: {item.text()}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载失败: {e}")

    def delete_selected_config(self):
        item = self.config_list.currentItem()
        if item and QMessageBox.question(self, "确认", f"确定删除 {item.text()}?") == QMessageBox.Yes:
            os.remove(os.path.join(CONFIG_DIR, item.text()))
            self.refresh_config_list()

    def add_row(self, data=None):
        row = TaskRow(self.task_layout, self.delete_row)
        if data: row.set_data(data)
        self.rows.append(row)

    def delete_row(self, row_widget):
        if row_widget in self.rows:
            self.rows.remove(row_widget)
            row_widget.deleteLater()

    def save_config(self):
        tasks = [row.get_data() for row in self.rows]
        path, _ = QFileDialog.getSaveFileName(self, "保存配置", CONFIG_DIR, "JSON Files (*.json)")
        if path:
            if not path.endswith(".json"): path += ".json"
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(tasks, f, indent=4, ensure_ascii=False)
            self.refresh_config_list()

    def start_task(self):
        tasks = [row.get_data() for row in self.rows if row.get_data()['value'] or row.get_data()['type'] == 5.0]
        if not tasks: return
        self.start_btn.setEnabled(False)
        self.showMinimized()
        self.worker = WorkerThread(self.engine, tasks, (self.loop_combo.currentText() == "循环执行"),
                                   self.window_combo.currentText())
        self.worker.log_signal.connect(lambda m: self.log_area.append(m))
        self.worker.finished_signal.connect(self.on_finished)
        self.worker.start()

    def stop_task(self):
        self.engine.stop()
        self.log_area.append(">>> 🔴 请求停止...")

    def on_finished(self):
        self.start_btn.setEnabled(True)
        self.showNormal()
        self.activateWindow()
        self.log_area.append(">>> 🏁 结束。")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    pyautogui.FAILSAFE = True
    window = RPAWindow()
    window.show()
    sys.exit(app.exec())