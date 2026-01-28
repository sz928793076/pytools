import sys
import os
import time
import json
import pyautogui
import pyperclip
import traceback
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                               QPushButton, QLabel, QComboBox, QLineEdit, QScrollArea,
                               QFileDialog, QTextEdit, QMessageBox, QFrame, QListWidget)
from PySide6.QtCore import Qt, QThread, Signal

# --------------------------
# 配置常量
# --------------------------
CONFIG_DIR = "configs"
if not os.path.exists(CONFIG_DIR):
    os.makedirs(CONFIG_DIR)


# --------------------------
# 核心逻辑 (鼠标键盘操作)
# --------------------------
def mouseClick(clickTimes, lOrR, img, reTry, timeout=60):
    start_time = time.time()
    while True:
        if timeout and (time.time() - start_time > timeout):
            print(f"等待图片 {img} 超时")
            return
        try:
            location = pyautogui.locateCenterOnScreen(img, confidence=0.9)
            if location is not None:
                pyautogui.click(location.x, location.y, clicks=clickTimes, interval=0.2, duration=0.2, button=lOrR)
                if reTry == 1: break
                if reTry > 1:
                    for _ in range(reTry - 1):
                        pyautogui.click(location.x, location.y, clicks=clickTimes, interval=0.2, duration=0.2,
                                        button=lOrR)
                    break
            if reTry == 1: break
        except:
            pass
        time.sleep(0.1)


def mouseMove(img, timeout=60):
    start_time = time.time()
    while True:
        if timeout and (time.time() - start_time > timeout): return
        try:
            location = pyautogui.locateCenterOnScreen(img, confidence=0.9)
            if location is not None:
                pyautogui.moveTo(location.x, location.y, duration=0.2)
                break
        except:
            pass
        time.sleep(0.1)


class RPAEngine:
    def __init__(self):
        self.is_running = False
        self.stop_requested = False

    def stop(self):
        self.stop_requested = True
        self.is_running = False

    def run_tasks(self, tasks, loop_forever=False, callback_msg=None):
        self.is_running = True
        self.stop_requested = False
        try:
            while True:
                for idx, task in enumerate(tasks):
                    if self.stop_requested:
                        if callback_msg: callback_msg("任务已停止")
                        return
                    cmd_type = task.get("type")
                    cmd_value = task.get("value")
                    retry = task.get("retry", 1)
                    if callback_msg: callback_msg(f"步骤 {idx + 1}: {cmd_value}")

                    if cmd_type == 1.0:
                        mouseClick(1, "left", cmd_value, retry)
                    elif cmd_type == 2.0:
                        mouseClick(2, "left", cmd_value, retry)
                    elif cmd_type == 3.0:
                        mouseClick(1, "right", cmd_value, retry)
                    elif cmd_type == 4.0:
                        pyperclip.copy(str(cmd_value))
                        pyautogui.hotkey('ctrl', 'v')
                        time.sleep(0.5)
                    elif cmd_type == 5.0:
                        time.sleep(float(cmd_value))
                    elif cmd_type == 6.0:
                        pyautogui.scroll(int(cmd_value))
                    elif cmd_type == 7.0:
                        keys = [k.strip() for k in str(cmd_value).lower().split('+')]
                        pyautogui.hotkey(*keys)
                    elif cmd_type == 8.0:
                        mouseMove(cmd_value)
                    elif cmd_type == 9.0:
                        path = str(cmd_value)
                        filename = os.path.join(path, f"screenshot_{time.strftime('%H%M%S')}.png") if os.path.isdir(
                            path) else path
                        pyautogui.screenshot(filename)

                if not loop_forever: break
                time.sleep(0.1)
        except Exception as e:
            if callback_msg: callback_msg(f"执行出错: {e}")
        finally:
            self.is_running = False
            if callback_msg: callback_msg("任务结束")


# --------------------------
# GUI 组件
# --------------------------
CMD_TYPES = {"左键单击": 1.0, "左键双击": 2.0, "右键单击": 3.0, "输入文本": 4.0, "等待(秒)": 5.0, "滚轮滑动": 6.0,
             "系统按键": 7.0, "鼠标悬停": 8.0, "截图保存": 9.0}
CMD_TYPES_REV = {v: k for k, v in CMD_TYPES.items()}


class WorkerThread(QThread):
    log_signal = Signal(str)
    finished_signal = Signal()

    def __init__(self, engine, tasks, loop_forever):
        super().__init__()
        self.engine, self.tasks, self.loop_forever = engine, tasks, loop_forever

    def run(self):
        self.engine.run_tasks(self.tasks, self.loop_forever, lambda m: self.log_signal.emit(m))
        self.finished_signal.emit()


class TaskRow(QFrame):
    def __init__(self, parent_layout, delete_callback):
        super().__init__()
        self.setFrameShape(QFrame.StyledPanel)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)

        self.type_combo = QComboBox()
        self.type_combo.addItems(list(CMD_TYPES.keys()))
        self.type_combo.currentTextChanged.connect(self.on_type_changed)
        layout.addWidget(self.type_combo)

        self.value_input = QLineEdit()
        layout.addWidget(self.value_input)

        self.file_btn = QPushButton("..")
        self.file_btn.setFixedWidth(30)
        self.file_btn.clicked.connect(self.select_file)
        layout.addWidget(self.file_btn)

        self.retry_input = QLineEdit("1")
        self.retry_input.setFixedWidth(40)
        layout.addWidget(self.retry_input)

        self.del_btn = QPushButton("×")
        self.del_btn.setFixedWidth(30)
        self.del_btn.clicked.connect(lambda: delete_callback(self))
        layout.addWidget(self.del_btn)

        parent_layout.insertWidget(parent_layout.count() - 1, self)
        self.on_type_changed(self.type_combo.currentText())

    def on_type_changed(self, text):
        cmd_type = CMD_TYPES[text]
        self.file_btn.setVisible(cmd_type in [1.0, 2.0, 3.0, 8.0, 9.0])
        self.retry_input.setVisible(cmd_type in [1.0, 2.0, 3.0, 8.0])

    def select_file(self):
        cmd_type = CMD_TYPES[self.type_combo.currentText()]
        if cmd_type == 9.0:
            path = QFileDialog.getExistingDirectory(self, "选择保存目录")
            if path: self.value_input.setText(path)
        else:
            path, _ = QFileDialog.getOpenFileName(self, "选择图片", "", "Images (*.png *.jpg)")
            if path: self.value_input.setText(path)

    def get_data(self):
        return {"type": CMD_TYPES[self.type_combo.currentText()], "value": self.value_input.text(),
                "retry": int(self.retry_input.text() or 1)}

    def set_data(self, data):
        self.type_combo.setCurrentText(CMD_TYPES_REV.get(data['type'], "左键单击"))
        self.value_input.setText(str(data.get('value', "")))
        self.retry_input.setText(str(data.get('retry', 1)))


class RPAWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("不高兴就喝水 RPA 配置工具")
        self.resize(1000, 650)
        self.engine = RPAEngine()
        self.rows = []
        self.worker = None

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_h_layout = QHBoxLayout(central_widget)

        # --- 左侧面板 ---
        self.left_panel = QVBoxLayout()
        self.left_panel.addWidget(QLabel("已存配置 (双击加载):"))

        self.config_list = QListWidget()
        self.config_list.setFixedWidth(200)
        self.config_list.itemDoubleClicked.connect(self.load_selected_config)
        self.left_panel.addWidget(self.config_list)

        # 按钮栏
        btn_layout = QHBoxLayout()
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(self.refresh_config_list)

        self.del_config_btn = QPushButton("删除配置")
        self.del_config_btn.setStyleSheet("color: #f44336;")
        self.del_config_btn.clicked.connect(self.delete_selected_config)

        btn_layout.addWidget(self.refresh_btn)
        btn_layout.addWidget(self.del_config_btn)
        self.left_panel.addLayout(btn_layout)

        self.main_h_layout.addLayout(self.left_panel, 1)

        # --- 右侧面板 ---
        self.right_panel = QVBoxLayout()

        top_bar = QHBoxLayout()
        self.add_btn = QPushButton("+ 新增步骤")
        self.add_btn.clicked.connect(self.add_row)
        top_bar.addWidget(self.add_btn)

        self.save_btn = QPushButton("保存当前配置")
        self.save_btn.clicked.connect(self.save_config)
        top_bar.addWidget(self.save_btn)

        top_bar.addStretch()
        self.loop_check = QComboBox()
        self.loop_check.addItems(["执行一次", "循环执行"])
        top_bar.addWidget(self.loop_check)

        self.start_btn = QPushButton("开始运行")
        self.start_btn.clicked.connect(self.start_task)
        self.start_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        top_bar.addWidget(self.start_btn)

        self.stop_btn = QPushButton("停止")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_task)
        top_bar.addWidget(self.stop_btn)
        self.right_panel.addLayout(top_bar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.task_container = QWidget()
        self.task_layout = QVBoxLayout(self.task_container)
        self.task_layout.addStretch()
        scroll.setWidget(self.task_container)
        self.right_panel.addWidget(scroll)

        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setMaximumHeight(120)
        self.right_panel.addWidget(QLabel("运行日志:"))
        self.right_panel.addWidget(self.log_area)

        self.main_h_layout.addLayout(self.right_panel, 4)

        self.refresh_config_list()
        self.add_row()

    # --- 配置列表逻辑 ---
    def refresh_config_list(self):
        self.config_list.clear()
        if not os.path.exists(CONFIG_DIR): return
        files = sorted([f for f in os.listdir(CONFIG_DIR) if f.endswith(".json")])
        self.config_list.addItems(files)

    def load_selected_config(self, item):
        full_path = os.path.join(CONFIG_DIR, item.text())
        self.perform_load(full_path)

    def delete_selected_config(self):
        """删除配置功能，带弹窗确认"""
        selected_item = self.config_list.currentItem()
        if not selected_item:
            QMessageBox.warning(self, "提示", "请先在列表中点击选择一个配置！")
            return

        filename = selected_item.text()
        full_path = os.path.join(CONFIG_DIR, filename)

        # 弹窗确认
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要永久删除配置 [{filename}] 吗？\n该操作无法撤销。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                os.remove(full_path)
                self.refresh_config_list()
                self.log_area.append(f"已删除配置: {filename}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"删除失败: {e}")

    # --- 业务逻辑 ---
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
        filename, _ = QFileDialog.getSaveFileName(self, "保存配置", CONFIG_DIR, "JSON (*.json)")
        if filename:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(tasks, f, indent=4, ensure_ascii=False)
            self.refresh_config_list()
            QMessageBox.information(self, "提示", "配置已保存")

    def perform_load(self, path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                tasks = json.load(f)
            for r in self.rows: r.deleteLater()
            self.rows.clear()
            for t in tasks: self.add_row(t)
            self.log_area.append(f"成功加载: {os.path.basename(path)}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载失败: {e}")

    def start_task(self):
        tasks = [row.get_data() for row in self.rows if row.get_data()['value']]
        if not tasks: return
        self.log_area.clear()
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.showMinimized()

        loop = (self.loop_check.currentText() == "循环执行")
        self.worker = WorkerThread(self.engine, tasks, loop)
        self.worker.log_signal.connect(lambda m: self.log_area.append(m))
        self.worker.finished_signal.connect(self.on_finished)
        self.worker.start()

    def stop_task(self):
        self.engine.stop()

    def on_finished(self):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.showNormal()
        self.activateWindow()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = RPAWindow()
    window.show()
    sys.exit(app.exec())