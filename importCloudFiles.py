import sys
import os
import json
import time
import re
import requests
from urllib.parse import quote
from PySide6.QtCore import QThread, Signal, QObject, QTimer, QMetaObject, Qt, Q_ARG
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QTextEdit, QLineEdit, QPushButton, QProgressBar,
    QPlainTextEdit, QSpinBox, QFileDialog, QMessageBox, QListWidget, QListWidgetItem
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


# ==================== 工作线程（多文件顺序上传） ====================
class MultiFileWorker(QObject):
    log_signal = Signal(str)
    progress_signal = Signal(int, int, float)
    time_signal = Signal(float, float)
    batch_result_signal = Signal(str, int, int, int)   # 文件名, 批次号, 期望条数, 实际插入条数
    file_finished_signal = Signal(str, int, int)       # 文件名, 应插入, 实际插入
    finished_signal = Signal(dict)

    def __init__(self, file_list, table, cookie, batch_size=100, max_retries=3):
        super().__init__()
        self.file_list = file_list          # [(文件路径, 表名), ...] 每个文件可单独指定表名
        self.table = table
        self.cookie = cookie
        self.batch_size = batch_size
        self.max_retries = max_retries
        self._is_running = True
        self.start_time = None

    def stop(self):
        self._is_running = False

    def _send_batch(self, batch, batch_idx, total, file_tag):
        """发送一个批次，返回 (是否成功, 实际插入条数, 批次原始数据)"""
        url = f"https://sf-sleye.lottery-sports.com/crondtask/InsertData?table={quote(self.table)}"
        headers = {
            "Content-Type": "application/json",
            "Cookie": self.cookie
        }
        try:
            body_json = json.dumps(batch, ensure_ascii=False)
        except Exception as e:
            self.log_signal.emit(f"❌ [{file_tag}] 批次 {batch_idx}/{total} 序列化失败: {e}")
            return False, 0, batch

        expected = len(batch)
        for attempt in range(1, self.max_retries + 1):
            if not self._is_running:
                return False, 0, batch
            try:
                resp = requests.post(url, data=body_json, headers=headers, timeout=30)
                # ===== 打印接口返回信息 =====
                resp_body = resp.text.strip()
                if len(resp_body) > 500:
                    resp_body = resp_body[:500] + f"...(共{len(resp.text)}字符)"
                self.log_signal.emit(
                    f"🧾 [{file_tag}] 批次 {batch_idx}/{total} → HTTP {resp.status_code} | 响应: {resp_body}"
                )
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
                except Exception:
                    pass

                if inserted != expected:
                    self.log_signal.emit(
                        f"⚠️ [{file_tag}] 批次 {batch_idx}/{total}: 服务器返回插入 {inserted} 条，本地 {expected} 条"
                    )
                return True, inserted, []
            except requests.exceptions.RequestException as e:
                if attempt < self.max_retries:
                    self.log_signal.emit(
                        f"⚠️ [{file_tag}] 批次 {batch_idx}/{total} 第{attempt}次请求失败: {e}，{2 ** attempt}秒后重试"
                    )
                    time.sleep(2 ** attempt)
                else:
                    self.log_signal.emit(f"❌ [{file_tag}] 批次 {batch_idx}/{total} 最终失败: {e}")
                    return False, 0, batch
            except Exception as e:
                self.log_signal.emit(f"❌ [{file_tag}] 批次 {batch_idx}/{total} 未知错误: {e}")
                return False, 0, batch
        return False, 0, batch

    def _load_file(self, path):
        """加载一个 JSON 数组文件，返回 list"""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            raise ValueError("文件内容不是 JSON 数组")
        return data

    def run(self):
        self.start_time = time.time()
        total_files = len(self.file_list)

        # 先统计所有文件总条数（用于全局进度）
        file_rows = {}
        for path, _ in self.file_list:
            try:
                self.log_signal.emit(f"📂 正在加载 {os.path.basename(path)} ...")
                data = self._load_file(path)
                file_rows[path] = data
                self.log_signal.emit(f"📂 {os.path.basename(path)} 加载完成，共 {len(data)} 条")
            except Exception as e:
                self.log_signal.emit(f"❌ 文件 {os.path.basename(path)} 加载失败，跳过: {e}")
                file_rows[path] = []
            if not self._is_running:
                break

        grand_total = sum(len(v) for v in file_rows.values())
        grand_batches = sum((len(v) + self.batch_size - 1) // self.batch_size for v in file_rows.values())
        self.log_signal.emit(
            f"共 {len(file_rows)} 个文件，有效数据 {grand_total} 条，总计 {grand_batches} 个批次（每批 {self.batch_size} 条）"
        )

        grand_inserted = 0
        grand_failed_rows = []
        file_reports = []
        global_batch_idx = 0

        for f_idx, (path, per_file_table) in enumerate(self.file_list, 1):
            if not self._is_running:
                break
            data = file_rows.get(path, [])
            fname = os.path.basename(path)
            if not data:
                self.log_signal.emit(f"⏭️ [{f_idx}/{total_files}] {fname} 无数据，跳过")
                continue

            self.log_signal.emit(f"\n========== [{f_idx}/{total_files}] 开始上传 {fname}（{len(data)} 条，表 {self.table}）==========")
            batches = [data[i:i + self.batch_size] for i in range(0, len(data), self.batch_size)]
            f_inserted = 0
            f_failed = []

            for idx, batch in enumerate(batches, 1):
                if not self._is_running:
                    self.log_signal.emit("用户主动停止")
                    break
                global_batch_idx += 1

                elapsed = time.time() - self.start_time
                if global_batch_idx > 1:
                    avg = elapsed / (global_batch_idx - 1)
                    remaining = avg * (grand_batches - global_batch_idx)
                else:
                    remaining = 0.0
                self.time_signal.emit(elapsed, remaining)
                self.progress_signal.emit(global_batch_idx, grand_batches, elapsed)

                success, inserted, failed_rows = self._send_batch(batch, idx, len(batches), fname)
                f_inserted += inserted
                self.batch_result_signal.emit(fname, idx, len(batch), inserted)
                if not success:
                    f_failed.append(idx)
                    grand_failed_rows.extend(failed_rows)

            self.log_signal.emit(
                f"✔️ [{f_idx}/{total_files}] {fname} 完成: 应插 {len(data)}，实插 {f_inserted}，失败批次 {f_failed if f_failed else '无'}"
            )
            file_reports.append({"file": fname, "expected": len(data), "inserted": f_inserted, "failed_batches": f_failed})
            self.file_finished_signal.emit(fname, len(data), f_inserted)
            grand_inserted += f_inserted
            data.clear()  # 释放内存

        final_elapsed = time.time() - self.start_time
        report = {
            "total_expected": grand_total,
            "total_inserted": grand_inserted,
            "lost": grand_total - grand_inserted,
            "failed_rows": grand_failed_rows,
            "file_reports": file_reports,
            "elapsed_seconds": final_elapsed
        }
        self.log_signal.emit(
            f"\n========== 最终统计 ==========\n"
            f"总耗时: {final_elapsed:.2f} 秒\n"
            f"应插入: {grand_total} 条\n实际插入: {grand_inserted} 条\n丢失: {grand_total - grand_inserted} 条"
        )
        for fr in file_reports:
            self.log_signal.emit(f"  {fr['file']}: {fr['inserted']}/{fr['expected']}，失败批次 {fr['failed_batches'] if fr['failed_batches'] else '无'}")
        self.finished_signal.emit(report)


# ==================== 主窗口 ====================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("JSON 文件批量导入工具")
        self.setMinimumSize(950, 800)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # 文件选择
        file_btn_layout = QHBoxLayout()
        file_btn_layout.addWidget(QLabel("JSON 文件（可多选）："))
        self.select_btn = QPushButton("选择文件")
        self.select_btn.clicked.connect(self.select_files)
        self.clear_btn = QPushButton("清空列表")
        self.clear_btn.clicked.connect(self.clear_files)
        self.remove_btn = QPushButton("移除选中")
        self.remove_btn.clicked.connect(self.remove_selected)
        file_btn_layout.addWidget(self.select_btn)
        file_btn_layout.addWidget(self.remove_btn)
        file_btn_layout.addWidget(self.clear_btn)
        file_btn_layout.addStretch()
        layout.addLayout(file_btn_layout)

        self.file_list_widget = QListWidget()
        self.file_list_widget.setSelectionMode(QListWidget.ExtendedSelection)
        self.file_list_widget.setFixedHeight(150)
        layout.addWidget(self.file_list_widget)

        # 参数行
        param_layout = QHBoxLayout()
        param_layout.addWidget(QLabel("table:"))
        self.table_edit = QLineEdit()
        self.table_edit.setPlaceholderText("从文件名自动识别，可手动修改（支持驼峰，自动转下划线）")
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
        self.start_btn = QPushButton("开始上传")
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

        self.selected_files = []   # [(路径, 表名 or None), ...]
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

    # ---------- 从文件名推断表名 ----------
    def guess_table_from_files(self, paths):
        bases = [os.path.splitext(os.path.basename(p))[0] for p in paths]
        if len(bases) == 1:
            name = bases[0]
        else:
            name = os.path.commonprefix(bases)
        # 去掉尾部日期/序号分隔符
        name = re.sub(r'[\-_0-9]+$', '', name)
        return self.camel_to_snake(name) if name else ""

    # ---------- 选择文件 ----------
    def select_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "选择 JSON 文件", "",
            "JSON Files (*.json);;All Files (*)"
        )
        if not paths:
            return
        added = 0
        for p in paths:
            if p not in [fp for fp, _ in self.selected_files]:
                self.selected_files.append((p, None))
                item = QListWidgetItem(f"{os.path.basename(p)}    [{os.path.getsize(p) / 1024 / 1024:.1f} MB]")
                item.setData(Qt.UserRole, p)
                item.setToolTip(p)
                self.file_list_widget.addItem(item)
                added += 1
        if added:
            self.log(f"已添加 {added} 个文件")
            # 自动填充表名（如果输入框为空或来自上次识别）
            guess = self.guess_table_from_files([fp for fp, _ in self.selected_files])
            if guess:
                self.table_edit.setText(guess)
                self.log(f"根据文件名自动识别表名: {guess}")

    def remove_selected(self):
        removed = 0
        for item in list(self.file_list_widget.selectedItems()):
            p = item.data(Qt.UserRole)
            self.selected_files = [x for x in self.selected_files if x[0] != p]
            self.file_list_widget.takeItem(self.file_list_widget.row(item))
            removed += 1
        if removed:
            self.log(f"已移除 {removed} 个文件")
            if self.selected_files:
                guess = self.guess_table_from_files([fp for fp, _ in self.selected_files])
                self.table_edit.setText(guess or "")
        else:
            self.log("请先在列表中选中要移除的文件")

    def clear_files(self):
        self.selected_files.clear()
        self.file_list_widget.clear()
        self.log("文件列表已清空")

    # ---------- 启动上传 ----------
    def start_request(self):
        table = self.table_edit.text().strip()
        cookie = self.cookie_edit.text().strip()
        batch_size = self.batch_spin.value()

        if not self.selected_files:
            self.log("错误：请先选择 JSON 文件")
            return
        if not table:
            self.log("错误：table 参数不能为空")
            return
        if not cookie:
            self.log("错误：Cookie 不能为空")
            return

        self.log_buffer.flush()
        self.time_label.setText("已用时间: 0.0 秒 | 预估剩余: 计算中...")

        # 为每个文件确定表名：若文件名包含全局表名前缀则用全局表名，否则单独识别
        file_list = []
        for path, _ in self.selected_files:
            file_list.append((path, None))

        self.thread = QThread()
        self.worker = MultiFileWorker(file_list, table, cookie, batch_size, max_retries=3)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.log_signal.connect(self.log)
        self.worker.progress_signal.connect(self.update_progress)
        self.worker.time_signal.connect(self.update_time_label)
        self.worker.batch_result_signal.connect(self.on_batch_result)
        self.worker.file_finished_signal.connect(self.on_file_finished)
        self.worker.finished_signal.connect(self.on_finished)
        self.worker.finished_signal.connect(self.thread.quit)
        self.worker.finished_signal.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

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

    def on_batch_result(self, fname, batch_idx, expected, inserted):
        if inserted < expected:
            self.log(f"⚠️ [{fname}] 批次 {batch_idx} 期望 {expected} 条，实际插入 {inserted} 条，丢失 {expected - inserted} 条")

    def on_file_finished(self, fname, expected, inserted):
        status = "✅" if inserted == expected else "⚠️"
        self.log(f"{status} 文件完成: {fname}  {inserted}/{expected}")

    def on_finished(self, report):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.last_report = report
        if report["lost"] > 0:
            self.export_btn.setEnabled(True)
            self.log(f"❌ 共丢失 {report['lost']} 条数据，可点击「导出失败数据」保存以便重试。")
        else:
            self.log("✅ 所有文件的所有数据均已成功插入！")

    def export_failed_data(self):
        if not self.last_report:
            QMessageBox.warning(self, "无数据", "没有可导出的失败数据报告")
            return
        data_to_export = self.last_report["failed_rows"]
        if not data_to_export:
            QMessageBox.information(self, "无数据", "没有失败的数据可导出")
            return
        file_path, _ = QFileDialog.getSaveFileName(self, "保存失败数据", "failed_rows.json", "JSON Files (*.json)")
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(data_to_export, f, ensure_ascii=False, indent=2)
                QMessageBox.information(self, "导出成功", f"已保存 {len(data_to_export)} 条失败数据到\n{file_path}")
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
