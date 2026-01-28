import sys
import re
import json
import requests
import pandas as pd
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QLineEdit, QPushButton, QTextEdit, QDateEdit,
                             QFormLayout, QMessageBox, QGroupBox)
from PyQt5.QtCore import QThread, pyqtSignal, QDate
from sqlalchemy import create_engine, text

# 数据库配置
DB_CONFIG = {
    'host': '127.0.0.1',
    'port': 3308,
    'user': 'root',
    'password': 'root',
    'database': 'sleyedb'
}


# 驼峰转下划线工具函数
def camel_to_snake(name):
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


# 工作线程：用于执行耗时任务，避免卡死界面
class Worker(QThread):
    log_signal = pyqtSignal(str)
    finish_signal = pyqtSignal()

    def __init__(self, task_type, params):
        super().__init__()
        self.task_type = task_type
        self.params = params

    def log(self, msg):
        self.log_signal.emit(msg)

    def get_data(self, url, cookie):
        headers = {
            "Cookie": cookie,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        try:
            self.log(f"正在请求接口: {url}")
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            # 兼容返回结构：有些接口直接返回list，有些可能在data字段里
            if isinstance(data, list):
                return data
            elif isinstance(data, dict) and 'data' in data and isinstance(data['data'], list):
                return data['data']
            elif isinstance(data, dict):
                # 如果是字典但不是标准结构，尝试直接转成单行列表
                return [data]
            return []
        except Exception as e:
            raise Exception(f"接口请求失败: {str(e)}")

    def run(self):
        try:
            cookie = self.params.get('cookie')
            start_date = self.params.get('start_date')  # yyyy-MM-dd
            end_date = self.params.get('end_date')  # yyyy-MM-dd

            # 用于文件名的日期格式 yyyyMMdd
            f_start = start_date.replace('-', '')
            f_end = end_date.replace('-', '')

            if self.task_type in ['api1', 'api2']:
                url_template = self.params.get('url')
                # 替换URL参数
                url = url_template.format(startDate=start_date, endDate=end_date)

                data = self.get_data(url, cookie)
                if not data:
                    self.log("接口返回数据为空，跳过导出。")
                    return

                df = pd.DataFrame(data)

                # 功能名
                func_name = "推送详情" if self.task_type == 'api1' else "推送组织"
                file_name = f"{func_name}-{f_start}-{f_end}.xlsx"

                df.to_excel(file_name, index=False)
                self.log(f"成功导出文件: {file_name}")

            elif self.task_type == 'db_sync':
                # 创建数据库连接
                self.log("正在连接数据库...")
                db_url = f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}?charset=utf8mb4"
                engine = create_engine(db_url)
                conn = engine.connect()

                # --- 第一步：同步 wechat_send_business_def ---
                url_def = "https://sleye-mobile.lottery.cn/api/wechat_send_business_def"
                data_def = self.get_data(url_def, cookie)
                if data_def:
                    df_def = pd.DataFrame(data_def)
                    # 驼峰转下划线
                    df_def.columns = [camel_to_snake(col) for col in df_def.columns]
                    self.log("正在同步表: wechat_send_business_def (先清空后写入)")
                    # 使用 replace 模式会自动 drop table 然后 create，相当于清空
                    df_def.to_sql('wechat_send_business_def', con=engine, if_exists='replace', index=False)
                else:
                    self.log("警告: wechat_send_business_def 接口无数据")

                # --- 第二步：同步 wechat_send_result ---
                url_res_tpl = "https://sleye-mobile.lottery.cn/api/wechat_send_result?sendTimeBEGIN={startDate}&sendTimeEND={endDate}"
                url_res = url_res_tpl.format(startDate=start_date, endDate=end_date)
                data_res = self.get_data(url_res, cookie)
                if data_res:
                    df_res = pd.DataFrame(data_res)
                    # 驼峰转下划线
                    df_res.columns = [camel_to_snake(col) for col in df_res.columns]
                    self.log("正在同步表: wechat_send_result (先清空后写入)")
                    df_res.to_sql('wechat_send_result', con=engine, if_exists='replace', index=False)
                else:
                    self.log("警告: wechat_send_result 接口无数据")

                # --- 第三步：执行SQL并导出 ---
                self.log("正在执行联合查询SQL...")
                sql_query = """
                SELECT 
                    wsr.business_type, 
                    wsr.business_no, 
                    wsbd.`business_name` AS '预警名称', 
                    wsr.send_person AS '发送人列表', 
                    (LENGTH(wsr.send_person) - LENGTH(REPLACE(wsr.send_person, '|', ''))) + 1 AS '人次', 
                    wsr.send_time AS '发送时间', 
                    wsr.content AS '发送内容' 
                FROM wechat_send_result wsr 
                LEFT JOIN `wechat_send_business_def` wsbd 
                ON wsr.`business_type` = wsbd.`business_type` 
                AND wsr.`business_no` = wsbd.`business_no` where wsr.business_type < 10000;
                """

                # 使用 pandas 直接读取 SQL
                df_result = pd.read_sql(text(sql_query), con=conn)

                # 导出文件
                file_name = f"数据库同步统计-{f_start}-{f_end}.xlsx"
                df_result.to_excel(file_name, index=False)
                self.log(f"数据库操作完成，结果已导出: {file_name}")

                conn.close()

        except Exception as e:
            self.log(f"错误: {str(e)}")
            import traceback
            traceback.print_exc()
        finally:
            self.finish_signal.emit()


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.worker = None

    def initUI(self):
        self.setWindowTitle('接口数据导出与数据库同步工具')
        self.setGeometry(100, 100, 800, 600)

        main_layout = QVBoxLayout()

        # 1. 配置区域
        config_group = QGroupBox("参数配置")
        form_layout = QFormLayout()

        # Cookie
        self.cookie_edit = QLineEdit()
        self.cookie_edit.setPlaceholderText("请输入Cookie")
        form_layout.addRow("Cookie:", self.cookie_edit)

        # URL 1
        self.url1_edit = QLineEdit()
        self.url1_edit.setText(
            "https://sleye-mobile.lottery.cn/api/v_wechat_send_snapshot_push_detail?triggerTimeBEGIN={startDate}&triggerTimeEND={endDate}")
        form_layout.addRow("URL模板 1 (详情):", self.url1_edit)

        # URL 2
        self.url2_edit = QLineEdit()
        self.url2_edit.setText(
            "https://sleye-mobile.lottery.cn/api/v_wechat_send_snapshot_push_organize?pushTimeBEGIN={startDate}&pushTimeEND={endDate}")
        form_layout.addRow("URL模板 2 (组织):", self.url2_edit)

        config_group.setLayout(form_layout)
        main_layout.addWidget(config_group)

        # 2. 时间选择
        date_group = QGroupBox("时间范围")
        date_layout = QHBoxLayout()

        date_layout.addWidget(QLabel("开始时间:"))
        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDisplayFormat("yyyy-MM-dd")
        self.start_date_edit.setDate(QDate.currentDate().addDays(-1))  # 默认昨天
        date_layout.addWidget(self.start_date_edit)

        date_layout.addWidget(QLabel("结束时间:"))
        self.end_date_edit = QDateEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDisplayFormat("yyyy-MM-dd")
        self.end_date_edit.setDate(QDate.currentDate())  # 默认今天
        date_layout.addWidget(self.end_date_edit)

        date_group.setLayout(date_layout)
        main_layout.addWidget(date_group)

        # 3. 按钮区域
        btn_layout = QHBoxLayout()

        self.btn_api1 = QPushButton("导出接口1 (推送详情)")
        self.btn_api1.clicked.connect(lambda: self.start_task('api1'))
        btn_layout.addWidget(self.btn_api1)

        self.btn_api2 = QPushButton("导出接口2 (推送组织)")
        self.btn_api2.clicked.connect(lambda: self.start_task('api2'))
        btn_layout.addWidget(self.btn_api2)

        self.btn_db = QPushButton("同步数据至数据库并导出统计")
        self.btn_db.setStyleSheet("background-color: #d1e7dd; color: #0f5132;")
        self.btn_db.clicked.connect(lambda: self.start_task('db_sync'))
        btn_layout.addWidget(self.btn_db)

        main_layout.addLayout(btn_layout)

        # 4. 日志输出
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        main_layout.addWidget(QLabel("执行日志:"))
        main_layout.addWidget(self.log_text)

        self.setLayout(main_layout)

    def log(self, msg):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {msg}")

    def get_params(self):
        return {
            'cookie': self.cookie_edit.text().strip(),
            'url1': self.url1_edit.text().strip(),
            'url2': self.url2_edit.text().strip(),
            'start_date': self.start_date_edit.date().toString("yyyy-MM-dd"),
            'end_date': self.end_date_edit.date().toString("yyyy-MM-dd")
        }

    def start_task(self, task_type):
        params = self.get_params()

        if not params['cookie']:
            QMessageBox.warning(self, "提示", "请填写Cookie")
            return

        # 锁定按钮
        self.btn_api1.setEnabled(False)
        self.btn_api2.setEnabled(False)
        self.btn_db.setEnabled(False)

        task_params = params.copy()
        if task_type == 'api1':
            task_params['url'] = params['url1']
        elif task_type == 'api2':
            task_params['url'] = params['url2']

        self.worker = Worker(task_type, task_params)
        self.worker.log_signal.connect(self.log)
        self.worker.finish_signal.connect(self.on_task_finished)
        self.worker.start()

    def on_task_finished(self):
        self.btn_api1.setEnabled(True)
        self.btn_api2.setEnabled(True)
        self.btn_db.setEnabled(True)
        self.log("任务执行结束。")
        QMessageBox.information(self, "完成", "操作已完成，请查看日志或目录文件。")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())