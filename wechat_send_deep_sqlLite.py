import sys
import os
import subprocess
import json
import pandas as pd
from datetime import datetime
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
import requests
import sqlite3
import warnings
from pathlib import Path

warnings.filterwarnings('ignore')


class DataExporter(QWidget):
    def __init__(self):
        super().__init__()
        self.db_path = "sleye_data.db"

        # --- 新增：定义省份映射字典 ---
        self.prov_map = {
            "0": "全国", "11": "北京", "12": "天津", "13": "河北", "14": "山西",
            "15": "内蒙古", "21": "辽宁", "22": "吉林", "23": "黑龙江", "31": "上海",
            "32": "江苏", "33": "浙江", "34": "安徽", "35": "福建", "36": "江西",
            "37": "山东", "41": "河南", "42": "湖北", "43": "湖南", "44": "广东",
            "45": "广西", "46": "海南", "50": "重庆", "51": "四川", "52": "贵州",
            "53": "云南", "54": "西藏", "61": "陕西", "62": "甘肃", "63": "青海",
            "64": "宁夏", "65": "新疆"
        }
        # ---------------------------

        self.initUI()
        self.load_cookie_from_file()
        self.cookie_update_timer = QTimer(self)
        self.cookie_update_timer.timeout.connect(self.update_cookie_from_file)
        self.cookie_update_timer.start(2000)


    def load_cookie_from_file(self):
        try:
            with open("cookie.txt", "r", encoding="utf-8") as f:
                cookie_str = f.read().strip()
            if cookie_str:
                self.cookie_input.setPlainText(cookie_str)
                self.log_message("已从 cookie.txt 自动加载 Cookie")
        except FileNotFoundError:
            self.log_message("未找到 cookie.txt，请先运行 Cookie 解析工具获取 Cookie")
        except Exception as e:
            self.log_message(f"加载 Cookie 失败: {str(e)}")

    def update_cookie_from_file(self):
        """定时读取 cookie.txt 并更新输入框"""
        try:
            with open("cookie.txt", "r", encoding="utf-8") as f:
                new_cookie = f.read().strip()
            current_cookie = self.cookie_input.toPlainText().strip()
            if new_cookie and new_cookie != current_cookie:
                self.cookie_input.setPlainText(new_cookie)
                self.log_message("Cookie已自动更新")
        except FileNotFoundError:
            pass  # 文件不存在时不提示
        except Exception as e:
            self.log_message(f"读取Cookie文件出错: {str(e)}")

    def closeEvent(self, event):
        """窗口关闭时停止定时器"""
        self.cookie_update_timer.stop()
        event.accept()

    def run_cookie_extractor(self):
        """执行当前目录下的 cookie_extractor.exe"""
        exe_path = os.path.join(os.getcwd(), "cookie_extractor.exe")
        if os.path.exists(exe_path):
            try:
                self.log_message(f"正在启动登录程序: {exe_path}")
                subprocess.Popen([exe_path], shell=True)
                QMessageBox.information(self, "提示", "登录程序已启动，请完成登录操作。")
            except Exception as e:
                self.log_message(f"启动登录程序失败: {str(e)}")
                QMessageBox.critical(self, "错误", f"启动登录程序失败:\n{str(e)}")
        else:
            self.log_message(f"未找到登录程序: {exe_path}")
            QMessageBox.critical(self, "错误", f"未找到登录程序:\n{exe_path}")

    def initUI(self):
        self.setWindowTitle('数据导出工具 (SQLite嵌入式数据库)')
        self.setGeometry(300, 100, 800, 700)

        main_layout = QVBoxLayout()

        # 新增登录按钮
        login_layout = QHBoxLayout()
        self.login_btn = QPushButton("登录获取Cookie")
        self.login_btn.setStyleSheet("background-color: #FF5722; color: white; padding: 8px; font-weight: bold;")
        self.login_btn.clicked.connect(self.run_cookie_extractor)
        login_layout.addWidget(self.login_btn)
        login_layout.addStretch()
        main_layout.addLayout(login_layout)

        # Cookie输入
        cookie_group = QGroupBox("Cookie设置")
        cookie_layout = QVBoxLayout()
        self.cookie_input = QTextEdit()
        self.cookie_input.setPlaceholderText("请输入Cookie...")
        self.cookie_input.setMaximumHeight(80)
        cookie_layout.addWidget(QLabel("Cookie:"))
        cookie_layout.addWidget(self.cookie_input)
        cookie_group.setLayout(cookie_layout)
        main_layout.addWidget(cookie_group)

        # URL模板1
        url1_group = QGroupBox("推送详情接口")
        url1_layout = QVBoxLayout()
        self.url1_input = QLineEdit()
        self.url1_input.setText(
            "https://sleye-mobile.lottery.cn/api/v_wechat_send_snapshot_push_detail?triggerTimeBEGIN={startDate}&triggerTimeEND={endDate}")
        url1_layout.addWidget(QLabel("URL模板:"))
        url1_layout.addWidget(self.url1_input)
        url1_group.setLayout(url1_layout)
        main_layout.addWidget(url1_group)

        # URL模板2
        url2_group = QGroupBox("推送组织接口")
        url2_layout = QVBoxLayout()
        self.url2_input = QLineEdit()
        self.url2_input.setText(
            "https://sleye-mobile.lottery.cn/api/v_wechat_send_snapshot_push_organize?pushTimeBEGIN={startDate}&pushTimeEND={endDate}")
        url2_layout.addWidget(QLabel("URL模板:"))
        url2_layout.addWidget(self.url2_input)
        url2_group.setLayout(url2_layout)
        main_layout.addWidget(url2_group)

        # 时间选择
        time_group = QGroupBox("时间范围")
        time_layout = QHBoxLayout()

        # 开始时间
        time_layout.addWidget(QLabel("开始时间:"))
        self.start_date_edit = QLineEdit()
        self.start_date_edit.setReadOnly(True)
        self.start_date_edit.setText(QDate.currentDate().addDays(-7).toString("yyyy-MM-dd"))
        time_layout.addWidget(self.start_date_edit)

        self.start_date_btn = QPushButton("选择")
        self.start_date_btn.clicked.connect(lambda: self.select_date(self.start_date_edit))
        time_layout.addWidget(self.start_date_btn)

        # 结束时间
        time_layout.addWidget(QLabel("结束时间:"))
        self.end_date_edit = QLineEdit()
        self.end_date_edit.setReadOnly(True)
        self.end_date_edit.setText(QDate.currentDate().toString("yyyy-MM-dd"))
        time_layout.addWidget(self.end_date_edit)

        self.end_date_btn = QPushButton("选择")
        self.end_date_btn.clicked.connect(lambda: self.select_date(self.end_date_edit))
        time_layout.addWidget(self.end_date_btn)

        time_layout.addStretch()
        time_group.setLayout(time_layout)
        main_layout.addWidget(time_group)

        # 数据库信息
        db_info_group = QGroupBox("数据库信息")
        db_info_layout = QVBoxLayout()

        file_layout = QHBoxLayout()
        file_layout.addWidget(QLabel("数据库文件:"))
        self.db_file_input = QLineEdit(self.db_path)
        self.db_file_input.setReadOnly(True)
        file_layout.addWidget(self.db_file_input)

        self.browse_btn = QPushButton("浏览...")
        self.browse_btn.clicked.connect(self.browse_db_file)
        file_layout.addWidget(self.browse_btn)
        db_info_layout.addLayout(file_layout)

        db_btn_layout = QHBoxLayout()
        self.init_db_btn = QPushButton("初始化数据库")
        self.init_db_btn.clicked.connect(self.init_database)
        self.init_db_btn.setStyleSheet("background-color: #9C27B0; color: white;")

        self.clear_db_btn = QPushButton("清空数据库")
        self.clear_db_btn.clicked.connect(self.clear_database)
        self.clear_db_btn.setStyleSheet("background-color: #F44336; color: white;")

        db_btn_layout.addWidget(self.init_db_btn)
        db_btn_layout.addWidget(self.clear_db_btn)
        db_btn_layout.addStretch()
        db_info_layout.addLayout(db_btn_layout)

        db_info_group.setLayout(db_info_layout)
        main_layout.addWidget(db_info_group)

        # 导出按钮区域
        export_group = QGroupBox("导出数据")
        export_layout = QHBoxLayout()

        self.export_btn1 = QPushButton("导出统计预警明细数据")
        self.export_btn1.setStyleSheet("background-color: #4CAF50; color: white; padding: 10px;")
        self.export_btn1.clicked.connect(self.export_data1)

        self.export_btn2 = QPushButton("导出统计预警合并统计数据")
        self.export_btn2.setStyleSheet("background-color: #2196F3; color: white; padding: 10px;")
        self.export_btn2.clicked.connect(self.export_data2)

        export_layout.addWidget(self.export_btn1)
        export_layout.addWidget(self.export_btn2)
        export_group.setLayout(export_layout)
        main_layout.addWidget(export_group)

        # 数据库同步
        db_group = QGroupBox("数据库同步")
        db_layout = QVBoxLayout()

        self.sync_btn = QPushButton("同步数据到SQLite数据库并导出结果")
        self.sync_btn.setStyleSheet("background-color: #FF9800; color: white; padding: 10px; font-weight: bold;")
        self.sync_btn.clicked.connect(self.sync_to_database)

        db_layout.addWidget(self.sync_btn)
        db_group.setLayout(db_layout)
        main_layout.addWidget(db_group)

        # 日志区域
        log_group = QGroupBox("操作日志")
        log_layout = QVBoxLayout()
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        log_layout.addWidget(self.log_text)
        log_group.setLayout(log_layout)
        main_layout.addWidget(log_group)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

        self.setLayout(main_layout)

    def select_date(self, target_edit):
        """弹出日历选择日期"""
        dialog = QDialog(self)
        dialog.setWindowTitle("选择日期")
        dialog.setModal(True)
        dialog_layout = QVBoxLayout(dialog)

        calendar = QCalendarWidget()
        calendar.setSelectedDate(QDate.fromString(target_edit.text(), "yyyy-MM-dd"))
        dialog_layout.addWidget(calendar)

        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("确定")
        cancel_btn = QPushButton("取消")
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        dialog_layout.addLayout(btn_layout)

        def on_ok():
            selected_date = calendar.selectedDate().toString("yyyy-MM-dd")
            target_edit.setText(selected_date)
            dialog.accept()

        ok_btn.clicked.connect(on_ok)
        cancel_btn.clicked.connect(dialog.reject)

        dialog.exec()

    def browse_db_file(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "选择数据库文件", self.db_path, "SQLite Database (*.db *.sqlite)"
        )
        if file_path:
            self.db_path = file_path
            self.db_file_input.setText(file_path)

    def get_connection(self):
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            return conn
        except Exception as e:
            self.log_message(f"数据库连接失败: {str(e)}")
            return None

    def init_database(self):
        conn = self.get_connection()
        if not conn:
            return
        try:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS wechat_send_business_def (
                    business_type INTEGER NOT NULL,
                    business_no INTEGER NOT NULL,
                    business_name TEXT NOT NULL,
                    trigger_time TEXT,
                    is_send INTEGER NOT NULL DEFAULT 1,
                    is_close INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (business_type, business_no)
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS wechat_send_result (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    business_type INTEGER NOT NULL,
                    business_no INTEGER NOT NULL,
                    send_person TEXT,
                    send_robot TEXT,
                    send_time TEXT NOT NULL,
                    snapshot_id TEXT,
                    content TEXT,
                    errcode INTEGER NOT NULL,
                    errmsg TEXT,
                    invalid_user TEXT NOT NULL,
                    UNIQUE(snapshot_id)
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_send_result_send_time ON wechat_send_result(send_time)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_send_result_business ON wechat_send_result(business_type, business_no)')
            conn.commit()
            self.log_message("数据库表结构初始化成功！")
            QMessageBox.information(self, "成功", "数据库表结构初始化成功！")
        except Exception as e:
            self.log_message(f"数据库初始化失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"数据库初始化失败: {str(e)}")
        finally:
            conn.close()

    def clear_database(self):
        reply = QMessageBox.question(
            self, "确认", "确定要清空所有数据吗？此操作不可恢复！",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            conn = self.get_connection()
            if not conn:
                return
            try:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM wechat_send_business_def")
                cursor.execute("DELETE FROM wechat_send_result")
                cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('wechat_send_business_def', 'wechat_send_result')")
                conn.commit()
                self.log_message("数据库数据已清空！")
                QMessageBox.information(self, "成功", "数据库数据已清空！")
            except Exception as e:
                self.log_message(f"清空数据库失败: {str(e)}")
                QMessageBox.critical(self, "错误", f"清空数据库失败: {str(e)}")
            finally:
                conn.close()

    def log_message(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
        QApplication.processEvents()

    def get_headers(self):
        cookie_text = self.cookie_input.toPlainText().strip()
        if not cookie_text:
            QMessageBox.warning(self, "警告", "请先输入Cookie！")
            return None
        return {
            'Cookie': cookie_text,
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

    def get_date_range(self):
        start = self.start_date_edit.text()
        end = self.end_date_edit.text()
        return start, end

    def fetch_data(self, url_template):
        headers = self.get_headers()
        if not headers:
            return None
        start_date, end_date = self.get_date_range()
        url = url_template.format(startDate=start_date, endDate=end_date)
        try:
            self.log_message(f"正在请求: {url}")
            response = requests.get(url, headers=headers, timeout=30)
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    self.log_message(f"获取到 {len(data)} 条数据")
                    return data
                else:
                    self.log_message(f"返回数据格式错误: {type(data)}")
                    return None
            else:
                self.log_message(f"请求失败: HTTP {response.status_code}")
                return None
        except Exception as e:
            self.log_message(f"请求异常: {str(e)}")
            return None

    def export_to_excel(self, data, filename_prefix):
        if not data:
            QMessageBox.warning(self, "警告", "没有数据可以导出！")
            return False
        start_date, end_date = self.get_date_range()
        start_str = start_date.replace("-", "")
        end_str = end_date.replace("-", "")
        filename = f"{filename_prefix}-{start_str}-{end_str}.xlsx"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存文件", filename, "Excel Files (*.xlsx)"
        )
        if file_path:
            try:
                df = pd.DataFrame(data)
                df.to_excel(file_path, index=False)
                self.log_message(f"数据已导出到: {file_path}")
                QMessageBox.information(self, "成功", f"数据已成功导出到:\n{file_path}")
                return True
            except Exception as e:
                self.log_message(f"导出失败: {str(e)}")
                QMessageBox.critical(self, "错误", f"导出失败: {str(e)}")
                return False
        return False

    def export_data1(self):
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(30)

        # 获取原始数据
        data = self.fetch_data(self.url1_input.text())

        self.progress_bar.setValue(70)

        if data:
            try:
                # 1. 转为 DataFrame
                df = pd.DataFrame(data)

                # 2. 映射 provName
                if 'provinceId' in df.columns:
                    # 确保 provinceId 转为字符串后进行映射
                    df['provName'] = df['provinceId'].astype(str).map(self.prov_map)
                    # 填充未匹配到的值为 '未知' (可选)
                    df['provName'] = df['provName'].fillna('未知')

                # 3. 【关键修改】将 DataFrame 转回字典列表，避免 export_to_excel 报错
                data_to_export = df.to_dict('records')

                # 4. 导出
                self.export_to_excel(data_to_export, "统计预警明细")

            except Exception as e:
                self.log_message(f"数据处理失败: {str(e)}")
                QMessageBox.critical(self, "错误", f"数据处理失败: {str(e)}")

        self.progress_bar.setValue(100)
        QTimer.singleShot(1000, lambda: self.progress_bar.setVisible(False))

    def export_data2(self):
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(30)
        data = self.fetch_data(self.url2_input.text())
        self.progress_bar.setValue(70)
        if data:
            self.export_to_excel(data, "统计预警合并统计")
        self.progress_bar.setValue(100)
        QTimer.singleShot(1000, lambda: self.progress_bar.setVisible(False))

    def camel_to_snake(self, name):
        import re
        name = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', name).lower()

    def format_datetime_for_sqlite(self, dt_str):
        try:
            formats = [
                '%Y-%m-%d %H:%M:%S',
                '%Y-%m-%dT%H:%M:%S',
                '%Y-%m-%dT%H:%M:%S.%f',
                '%Y/%m/%d %H:%M:%S'
            ]
            for fmt in formats:
                try:
                    dt = datetime.strptime(dt_str, fmt)
                    return dt.isoformat()
                except ValueError:
                    continue
            return dt_str
        except:
            return dt_str

    def sync_to_database(self):
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        if not Path(self.db_path).exists():
            self.log_message("数据库文件不存在，正在初始化...")
            self.init_database()
        headers = self.get_headers()
        if not headers:
            self.progress_bar.setVisible(False)
            return
        try:
            conn = self.get_connection()
            if not conn:
                return
            # 同步business_def
            business_def_url = "https://sleye-mobile.lottery.cn/api/wechat_send_business_def"
            response = requests.get(business_def_url, headers=headers, timeout=30)
            if response.status_code == 200:
                business_data = response.json()
                if isinstance(business_data, list):
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM wechat_send_business_def")
                    for item in business_data:
                        snake_item = {self.camel_to_snake(k): v for k, v in item.items()}
                        cursor.execute('''
                            INSERT OR REPLACE INTO wechat_send_business_def 
                            (business_type, business_no, business_name, trigger_time, is_send, is_close)
                            VALUES (?, ?, ?, ?, ?, ?)
                        ''', (
                            snake_item.get('business_type') or 0,
                            snake_item.get('business_no') or 0,
                            snake_item.get('business_name') or '',
                            snake_item.get('trigger_time'),
                            snake_item.get('is_send', 1),
                            snake_item.get('is_close', 0)
                        ))
                    conn.commit()
                    self.log_message(f"wechat_send_business_def表同步完成，{len(business_data)}条记录")
            # 同步send_result
            start_date, end_date = self.get_date_range()
            send_result_url = f"https://sleye-mobile.lottery.cn/api/wechat_send_result?sendTimeBEGIN={start_date}&sendTimeEND={end_date}"
            response = requests.get(send_result_url, headers=headers, timeout=30)
            if response.status_code == 200:
                send_result_data = response.json()
                if isinstance(send_result_data, list):
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM wechat_send_result")
                    inserted_count = 0
                    for item in send_result_data:
                        snake_item = {self.camel_to_snake(k): v for k, v in item.items()}
                        send_time = self.format_datetime_for_sqlite(snake_item.get('send_time', ''))
                        cursor.execute('''
                            INSERT OR IGNORE INTO wechat_send_result 
                            (business_type, business_no, send_person, send_robot, send_time, snapshot_id, content, errcode, errmsg, invalid_user)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            snake_item.get('business_type', 0),
                            snake_item.get('business_no', 0),
                            snake_item.get('send_person'),
                            snake_item.get('send_robot'),
                            send_time,
                            snake_item.get('snapshot_id'),
                            snake_item.get('content'),
                            snake_item.get('errcode', 0),
                            snake_item.get('errmsg'),
                            snake_item.get('invalid_user', '')
                        ))
                        inserted_count += cursor.rowcount
                    conn.commit()
                    self.log_message(f"wechat_send_result表同步完成，{len(send_result_data)}条记录，成功插入{inserted_count}条")
            # 查询导出
            sql = """
            SELECT 
                wsr.business_type, 
                wsr.business_no, 
                wsbd.`business_name` '预警名称', 
                wsr.send_person '发送人列表', 
                (LENGTH(wsr.send_person) - LENGTH(REPLACE(wsr.send_person, '|', ''))) + 1 '人次', 
                wsr.send_time '发送时间', 
                wsr.content '发送内容' 
            FROM wechat_send_result wsr 
            LEFT JOIN `wechat_send_business_def` wsbd 
                ON wsr.`business_type` = wsbd.`business_type` 
                AND wsr.`business_no` = wsbd.`business_no` 
            WHERE wsr.business_type < 10000
            """
            df_result = pd.read_sql(sql, conn)
            if not df_result.empty:
                filename = f"统计老预警-{start_date.replace('-','')}-{end_date.replace('-','')}.xlsx"
                file_path, _ = QFileDialog.getSaveFileName(self, "保存查询结果", filename, "Excel Files (*.xlsx)")
                if file_path:
                    df_result.to_excel(file_path, index=False)
                    self.log_message(f"查询结果已导出到: {file_path}")
                    QMessageBox.information(self, "成功", f"同步完成，导出{len(df_result)}条记录。")
            else:
                QMessageBox.information(self, "提示", "查询结果为空。")
        except Exception as e:
            self.log_message(f"同步过程中出现错误: {str(e)}")
            QMessageBox.critical(self, "错误", f"同步失败: {str(e)}")
        finally:
            if 'conn' in locals():
                conn.close()
            QTimer.singleShot(1000, lambda: self.progress_bar.setVisible(False))


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    exporter = DataExporter()
    exporter.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()