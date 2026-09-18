import sys
import json
import time
import re
import requests
from urllib.parse import quote
from PySide6.QtCore import QThread, Signal, QObject, QTimer, QMetaObject, Qt, Q_ARG
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QTextEdit, QLineEdit, QPushButton, QProgressBar,
    QPlainTextEdit, QSpinBox, QFileDialog, QMessageBox
)
from collections import deque


# ==================== 日志缓冲区 ====================
class LogBuffer(QObject):
    def __init__(self, flush_interval_ms=150):
        super().__init__()
        self.buffer = deque()
        self.flush_interval = flush_interval_ms
        self.timer = QTimer()
        self.timer.timeout.connect(self.flush)
        self.widget = None

    def attach(self, text_widget):
        self.widget = text_widget
        self.timer.start(self.flush_interval)

    def append(self, text):
        self.buffer.append(text)
        if len(self.buffer) > 30:
            self.flush()

    def flush(self):
        if not self.widget or not self.buffer:
            return
        texts = []
        while self.buffer:
            texts.append(self.buffer.popleft())
        if texts:
            QMetaObject.invokeMethod(
                self.widget, "appendPlainText",
                Qt.QueuedConnection,
                Q_ARG(str, "\n".join(texts))
            )
            sb = self.widget.verticalScrollBar()
            QMetaObject.invokeMethod(
                sb, "setValue",
                Qt.QueuedConnection,
                Q_ARG(int, sb.maximum())
            )

    def stop(self):
        self.timer.stop()
        self.flush()


# ==================== 工作线程 ====================
class RequestWorker(QObject):
    log_signal = Signal(str)
    progress_signal = Signal(int, int, float)
    time_signal = Signal(float, float)
    batch_result_signal = Signal(int, int, int)
    finished_signal = Signal(dict)

    def __init__(self, valid_data, table, cookie, batch_size=100, max_retries=3):
        super().__init__()
        self.valid_data = valid_data
        self.table = table
        self.cookie = cookie
        self.batch_size = batch_size
        self.max_retries = max_retries
        self._is_running = True
        self.start_time = None

    def stop(self):
        self._is_running = False

    def _serialize_batch(self, batch):
        try:
            return json.dumps(batch, ensure_ascii=False)
        except Exception as e:
            self.log_signal.emit(f"序列化失败: {e}")
            return None

    def _send_batch(self, batch, batch_idx, total):
        url = f"https://sf-sleye.lottery-sports.com/crondtask/InsertData?table={quote(self.table)}"
        headers = {
            "Content-Type": "application/json",
            "Cookie": self.cookie
        }
        body_json = self._serialize_batch(batch)
        if body_json is None:
            return False, 0

        expected = len(batch)
        for attempt in range(1, self.max_retries + 1):
            if not self._is_running:
                return False, 0
            try:
                resp = requests.post(url, data=body_json, headers=headers, timeout=30)
                resp.raise_for_status()
                inserted = expected
                try:
                    resp_json = resp.json()
                    if isinstance(resp_json, dict):
                        if "inserted" in resp_json:
                            inserted = int(resp_json["inserted"])
                        elif "data" in resp_json and isinstance(resp_json["data"], dict) and "inserted" in resp_json["data"]:
                            inserted = int(resp_json["data"]["inserted"])
                        elif "inserted_count" in resp_json:
                            inserted = int(resp_json["inserted_count"])
                except:
                    pass
                if inserted != expected:
                    self.log_signal.emit(
                        f"⚠️ 批次 {batch_idx}/{total}: 服务器返回插入 {inserted} 条，本地 {expected} 条"
                    )
                return True, inserted
            except requests.exceptions.RequestException as e:
                if attempt < self.max_retries:
                    time.sleep(2 ** attempt)
                else:
                    self.log_signal.emit(f"❌ 批次 {batch_idx}/{total} 最终失败: {e}")
                    return False, 0
            except Exception as e:
                self.log_signal.emit(f"❌ 批次 {batch_idx}/{total} 未知错误: {e}")
                return False, 0
        return False, 0

    def run(self):
        batches = [self.valid_data[i:i+self.batch_size] for i in range(0, len(self.valid_data), self.batch_size)]
        total_batches = len(batches)
        total_expected = len(self.valid_data)
        total_inserted = 0
        failed_batches = []

        self.start_time = time.time()
        self.log_signal.emit(f"有效数据共 {total_expected} 条，拆分为 {total_batches} 个批次（每批最多 {self.batch_size} 条）")
        self.progress_signal.emit(0, total_batches, 0.0)

        for idx, batch in enumerate(batches, 1):
            if not self._is_running:
                self.log_signal.emit("用户主动停止")
                break

            elapsed = time.time() - self.start_time
            if idx > 1:
                avg_time_per_batch = elapsed / (idx - 1)
                remaining_batches = total_batches - idx
                remaining_sec = avg_time_per_batch * remaining_batches
            else:
                remaining_sec = 0.0
            self.time_signal.emit(elapsed, remaining_sec)
            self.progress_signal.emit(idx, total_batches, elapsed)

            if idx % 5 == 0 or idx == 1 or idx == total_batches:
                self.log_signal.emit(f"▶️ 发送批次 {idx}/{total_batches} ({len(batch)} 条)")

            success, inserted = self._send_batch(batch, idx, total_batches)
            total_inserted += inserted
            self.batch_result_signal.emit(idx, len(batch), inserted)

            if not success:
                failed_batches.append(idx)

        final_elapsed = time.time() - self.start_time
        report = {
            "total_expected": total_expected,
            "total_inserted": total_inserted,
            "lost": total_expected - total_inserted,
            "failed_batches": failed_batches,
            "all_data": self.valid_data,
            "elapsed_seconds": final_elapsed
        }
        self.log_signal.emit(
            f"\n========== 最终统计 ==========\n"
            f"总耗时: {final_elapsed:.2f} 秒\n"
            f"应插入: {total_expected} 条\n实际插入: {total_inserted} 条\n丢失: {total_expected - total_inserted} 条\n"
            f"失败批次: {failed_batches if failed_batches else '无'}"
        )
        self.finished_signal.emit(report)


# ==================== 主窗口 ====================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("批量插入工具（无驼峰校验）")
        self.setMinimumSize(900, 750)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # JSON 输入
        layout.addWidget(QLabel("JSON 数组（原始数据）："))
        self.json_edit = QTextEdit()
        self.json_edit.setPlaceholderText('粘贴一个很长的 JSON 数组，例如：[{"draw_id":"1"}, ...]')
        layout.addWidget(self.json_edit)

        # 参数行
        param_layout = QHBoxLayout()
        param_layout.addWidget(QLabel("table:"))
        self.table_edit = QLineEdit()
        self.table_edit.setPlaceholderText("game_draw  (支持驼峰，自动转下划线)")
        param_layout.addWidget(self.table_edit)
        param_layout.addWidget(QLabel("批次大小:"))
        self.batch_spin = QSpinBox()
        self.batch_spin.setRange(1, 500)
        self.batch_spin.setValue(100)
        param_layout.addWidget(self.batch_spin)
        layout.addLayout(param_layout)

        # Cookie
        layout.addWidget(QLabel("Cookie（完整字符串）："))
        self.cookie_edit = QLineEdit()
        layout.addWidget(self.cookie_edit)

        # 按钮行
        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("开始发送")
        self.start_btn.clicked.connect(self.start_request)
        self.stop_btn = QPushButton("停止")
        self.stop_btn.clicked.connect(self.stop_request)
        self.stop_btn.setEnabled(False)
        self.export_btn = QPushButton("导出失败数据")
        self.export_btn.clicked.connect(self.export_failed_data)
        self.export_btn.setEnabled(False)
        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.stop_btn)
        btn_layout.addWidget(self.export_btn)
        layout.addLayout(btn_layout)

        # 进度条及时间显示
        progress_layout = QVBoxLayout()
        self.progress_bar = QProgressBar()
        progress_layout.addWidget(self.progress_bar)
        self.time_label = QLabel("已用时间: 0.0 秒 | 预估剩余: 等待开始")
        progress_layout.addWidget(self.time_label)
        layout.addLayout(progress_layout)

        # 日志输出
        layout.addWidget(QLabel("日志输出："))
        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)

        # 日志缓冲
        self.log_buffer = LogBuffer(flush_interval_ms=150)
        self.log_buffer.attach(self.log_text)

        # table 输入框自动转换驼峰
        self._table_updating = False
        self.table_edit.textChanged.connect(self.on_table_text_changed)

        self.thread = None
        self.worker = None
        self.last_report = None

    def log(self, msg):
        self.log_buffer.append(msg)

    # ---------- 驼峰转下划线（仅用于 table 参数） ----------
    def camel_to_snake(self, name):
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

    def on_table_text_changed(self):
        if self._table_updating:
            return
        text = self.table_edit.text()
        if any(c.isupper() for c in text):
            self._table_updating = True
            converted = self.camel_to_snake(text)
            self.table_edit.setText(converted)
            self.table_edit.setCursorPosition(len(converted))
            self._table_updating = False

    # ---------- 过滤不可序列化的数据 ----------
    def validate_and_filter_data(self, data_array):
        valid = []
        invalid_indices = []
        for i, item in enumerate(data_array):
            try:
                json.dumps(item, ensure_ascii=False)
                valid.append(item)
            except Exception as e:
                invalid_indices.append(i)
                self.log(f"⚠️ 索引 {i} 的数据无法序列化，已跳过。错误: {e}")
        if invalid_indices:
            self.log(f"共跳过 {len(invalid_indices)} 条不可序列化的数据。")
        return valid

    # ---------- 启动请求 ----------
    def start_request(self):
        json_text = self.json_edit.toPlainText().strip()
        table = self.table_edit.text().strip()
        cookie = self.cookie_edit.text().strip()
        batch_size = self.batch_spin.value()

        if not json_text:
            self.log("错误：JSON 数组不能为空")
            return
        if not table:
            self.log("错误：table 参数不能为空")
            return
        if not cookie:
            self.log("错误：Cookie 不能为空")
            return

        try:
            raw_data = json.loads(json_text)
        except json.JSONDecodeError as e:
            self.log(f"错误：JSON 解析失败 - {e}")
            return

        if not isinstance(raw_data, list):
            self.log("错误：输入必须是 JSON 数组（以 [ 开头 ] 结尾）")
            return

        if len(raw_data) == 0:
            self.log("警告：数组为空")
            return

        # 过滤不可序列化数据（不再检查驼峰）
        valid_data = self.validate_and_filter_data(raw_data)
        if not valid_data:
            self.log("错误：没有有效数据可以发送")
            return

        self.log(f"原始数据 {len(raw_data)} 条，过滤后有效数据 {len(valid_data)} 条")

        # 清空旧日志缓冲区
        self.log_buffer.flush()

        # 重置时间显示
        self.time_label.setText("已用时间: 0.0 秒 | 预估剩余: 计算中...")

        # 创建工作线程
        self.thread = QThread()
        self.worker = RequestWorker(valid_data, table, cookie, batch_size, max_retries=3)
        self.worker.moveToThread(self.thread)

        # 连接信号
        self.thread.started.connect(self.worker.run)
        self.worker.log_signal.connect(self.log)
        self.worker.progress_signal.connect(self.update_progress)
        self.worker.time_signal.connect(self.update_time_label)
        self.worker.batch_result_signal.connect(self.on_batch_result)
        self.worker.finished_signal.connect(self.on_finished)
        self.worker.finished_signal.connect(self.thread.quit)
        self.worker.finished_signal.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        # 界面状态
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.export_btn.setEnabled(False)
        self.progress_bar.setValue(0)

        self.thread.start()

    def stop_request(self):
        if self.worker:
            self.worker.stop()
            self.log("正在停止...")
            self.stop_btn.setEnabled(False)

    def update_progress(self, current, total, elapsed):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        QApplication.processEvents()

    def update_time_label(self, elapsed, remaining):
        self.time_label.setText(f"已用时间: {elapsed:.1f} 秒 | 预估剩余: {remaining:.1f} 秒")

    def on_batch_result(self, batch_idx, expected, inserted):
        if inserted < expected:
            self.log(f"⚠️ 批次 {batch_idx} 期望 {expected} 条，实际插入 {inserted} 条，丢失 {expected - inserted} 条")

    def on_finished(self, report):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.last_report = report
        if report["lost"] > 0:
            self.export_btn.setEnabled(True)
            self.log(f"❌ 共丢失 {report['lost']} 条数据，可点击「导出失败数据」保存原始数据以便重试。")
        else:
            self.log("✅ 所有数据均已成功插入！")

    def export_failed_data(self):
        if not self.last_report:
            QMessageBox.warning(self, "无数据", "没有可导出的失败数据报告")
            return
        data_to_export = self.last_report["all_data"]
        if not data_to_export:
            QMessageBox.information(self, "无数据", "没有有效数据可导出")
            return
        file_path, _ = QFileDialog.getSaveFileName(self, "保存失败数据", "failed_data.json", "JSON Files (*.json)")
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(data_to_export, f, ensure_ascii=False, indent=2)
                QMessageBox.information(self, "导出成功", f"已保存 {len(data_to_export)} 条数据到\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "导出失败", str(e))

    def closeEvent(self, event):
        self.log_buffer.stop()
        event.accept()


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()