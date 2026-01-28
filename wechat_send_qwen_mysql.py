import sys
import re
import json
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QDateEdit, QMessageBox, QTextEdit
)
from PyQt6.QtCore import QDate, Qt
import requests
import pandas as pd
import pymysql


def camel_to_snake(name):
    """将驼峰命名转换为下划线命名，如 businessType -> business_type"""
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


class WeChatSyncTool(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("微信推送数据同步工具")
        self.resize(850, 600)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        # Cookie 输入
        cookie_layout = QHBoxLayout()
        cookie_layout.addWidget(QLabel("Cookie:"))
        self.cookie_input = QLineEdit()
        cookie_layout.addWidget(self.cookie_input)
        layout.addLayout(cookie_layout)

        # URL 模板1
        url1_layout = QHBoxLayout()
        url1_layout.addWidget(QLabel("详情接口模板:"))
        self.url1_input = QLineEdit(
            "https://sleye-mobile.lottery.cn/api/v_wechat_send_snapshot_push_detail?triggerTimeBEGIN={startDate}&triggerTimeEND={endDate}"
        )
        url1_layout.addWidget(self.url1_input)
        layout.addLayout(url1_layout)

        # URL 模板2
        url2_layout = QHBoxLayout()
        url2_layout.addWidget(QLabel("组织接口模板:"))
        self.url2_input = QLineEdit(
            "https://sleye-mobile.lottery.cn/api/v_wechat_send_snapshot_push_organize?pushTimeBEGIN={startDate}&pushTimeEND={endDate}"
        )
        url2_layout.addWidget(self.url2_input)
        layout.addLayout(url2_layout)

        # 日期选择（强制格式为 yyyy-MM-dd）
        date_layout = QHBoxLayout()
        date_layout.addWidget(QLabel("开始时间 (yyyy-MM-dd):"))
        self.start_date = QDateEdit()
        self.start_date.setDisplayFormat("yyyy-MM-dd")
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(QDate.currentDate().addDays(-7))
        date_layout.addWidget(self.start_date)

        date_layout.addWidget(QLabel("结束时间 (yyyy-MM-dd):"))
        self.end_date = QDateEdit()
        self.end_date.setDisplayFormat("yyyy-MM-dd")
        self.end_date.setCalendarPopup(True)
        self.end_date.setDate(QDate.currentDate())
        date_layout.addWidget(self.end_date)
        layout.addLayout(date_layout)

        # 按钮区域
        btn_layout = QHBoxLayout()
        self.btn_export1 = QPushButton("导出详情数据")
        self.btn_export2 = QPushButton("导出组织数据")
        self.btn_sync_all = QPushButton("同步并导出汇总报表")
        btn_layout.addWidget(self.btn_export1)
        btn_layout.addWidget(self.btn_export2)
        btn_layout.addWidget(self.btn_sync_all)
        layout.addLayout(btn_layout)

        # 日志输出
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)

        self.setLayout(layout)

        # 绑定事件
        self.btn_export1.clicked.connect(self.export_detail)
        self.btn_export2.clicked.connect(self.export_organize)
        self.btn_sync_all.clicked.connect(self.sync_and_export_summary)

    def log(self, msg):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {msg}")
        QApplication.processEvents()

    def get_headers(self):
        cookie = self.cookie_input.text().strip()
        if not cookie:
            raise ValueError("Cookie 不能为空")
        return {"Cookie": cookie}

    def get_date_str(self, qdate):
        return qdate.toString("yyyy-MM-dd")

    def get_short_date_str(self, qdate):
        return qdate.toString("yyyyMMdd")

    def fetch_and_export(self, url_template, base_name):
        try:
            headers = self.get_headers()
            start_qdate = self.start_date.date()
            end_qdate = self.end_date.date()
            start_str = self.get_date_str(start_qdate)
            end_str = self.get_date_str(end_qdate)

            url = url_template.replace("{startDate}", start_str).replace("{endDate}", end_str)
            self.log(f"请求接口: {url}")
            resp = requests.get(url, headers=headers, timeout=20)
            resp.raise_for_status()
            data = resp.json()
            if not isinstance(data, list):
                raise ValueError("接口返回数据不是 JSON 数组")

            # 生成文件名：功能名-开始时间-结束时间.xlsx
            short_start = self.get_short_date_str(start_qdate)
            short_end = self.get_short_date_str(end_qdate)
            filename = f"{base_name}-{short_start}-{short_end}.xlsx"

            df = pd.DataFrame(data)
            df.to_excel(filename, index=False, engine='openpyxl')
            self.log(f"✅ 成功导出: {filename}")
            QMessageBox.information(self, "成功", f"已保存为:\n{filename}")
        except Exception as e:
            error_msg = f"导出失败: {str(e)}"
            self.log(f"❌ {error_msg}")
            QMessageBox.critical(self, "错误", error_msg)

    def export_detail(self):
        self.fetch_and_export(self.url1_input.text(), "push_detail")

    def export_organize(self):
        self.fetch_and_export(self.url2_input.text(), "push_organize")

    def sync_and_export_summary(self):
        db_config = {
            'host': '127.0.0.1',
            'port': 3308,
            'user': 'root',
            'password': 'root',
            'database': 'sleyedb',
            'charset': 'utf8mb4',
            'autocommit': True
        }

        try:
            headers = self.get_headers()
            start_qdate = self.start_date.date()
            end_qdate = self.end_date.date()
            start_str = self.get_date_str(start_qdate)
            end_str = self.get_date_str(end_qdate)

            # === 1. 同步 wechat_send_business_def (无参) ===
            self.log("正在同步 wechat_send_business_def...")
            resp1 = requests.get(
                "https://sleye-mobile.lottery.cn/api/wechat_send_business_def",
                headers=headers,
                timeout=20
            )
            resp1.raise_for_status()
            data1 = resp1.json()
            if not isinstance(data1, list):
                raise ValueError("business_def 接口返回非数组")

            converted1 = [{camel_to_snake(k): v for k, v in item.items()} for item in data1]
            self.write_to_table(db_config, "wechat_send_business_def", converted1)
            self.log("✅ wechat_send_business_def 同步完成")

            # === 2. 同步 wechat_send_result (带时间参数) ===
            url2 = f"https://sleye-mobile.lottery.cn/api/wechat_send_result?sendTimeBEGIN={start_str}&sendTimeEND={end_str}"
            self.log(f"请求: {url2}")
            resp2 = requests.get(url2, headers=headers, timeout=20)
            resp2.raise_for_status()
            data2 = resp2.json()
            if not isinstance(data2, list):
                raise ValueError("wechat_send_result 接口返回非数组")

            converted2 = [{camel_to_snake(k): v for k, v in item.items()} for item in data2]
            self.write_to_table(db_config, "wechat_send_result", converted2)
            self.log("✅ wechat_send_result 同步完成")

            # === 3. 执行汇总查询 ===
            self.log("正在执行汇总 SQL 查询...")
            conn = pymysql.connect(**db_config)
            cursor = conn.cursor(pymysql.cursors.DictCursor)

            query = """
            SELECT 
                wsr.business_type, 
                wsr.business_no, 
                wsbd.business_name AS `预警名称`, 
                wsr.send_person AS `发送人列表`, 
                (LENGTH(wsr.send_person) - LENGTH(REPLACE(wsr.send_person, '|', ''))) + 1 AS `人次`, 
                wsr.send_time AS `发送时间`, 
                wsr.content AS `发送内容`
            FROM wechat_send_result wsr 
            LEFT JOIN wechat_send_business_def wsbd 
                ON wsr.business_type = wsbd.business_type 
                AND wsr.business_no = wsbd.business_no
            WHERE wsr.business_type < 10000
            """
            cursor.execute(query)
            result = cursor.fetchall()
            conn.close()

            if not result:
                self.log("⚠️ 汇总查询无结果")
                df_summary = pd.DataFrame()
            else:
                df_summary = pd.DataFrame(result)

            # 生成文件名
            short_start = self.get_short_date_str(start_qdate)
            short_end = self.get_short_date_str(end_qdate)
            summary_filename = f"summary_report-{short_start}-{short_end}.xlsx"
            df_summary.to_excel(summary_filename, index=False, engine='openpyxl')
            self.log(f"✅ 汇总报表已导出: {summary_filename}")
            QMessageBox.information(self, "成功", f"同步完成！汇总报表:\n{summary_filename}")

        except Exception as e:
            error_msg = f"同步失败: {str(e)}"
            self.log(f"❌ {error_msg}")
            QMessageBox.critical(self, "错误", error_msg)

    def write_to_table(self, db_config, table, data_list):
        if not data_list:
            self.log(f"⚠️ 表 {table} 无数据，跳过写入")
            return

        conn = pymysql.connect(**db_config)
        cursor = conn.cursor()

        # 清空表
        cursor.execute(f"TRUNCATE TABLE `{table}`")

        # 获取字段
        columns = list(data_list[0].keys())
        placeholders = ', '.join(['%s'] * len(columns))
        columns_str = ', '.join([f"`{col}`" for col in columns])
        insert_sql = f"INSERT INTO `{table}` ({columns_str}) VALUES ({placeholders})"

        # 准备数据
        values = []
        for row in data_list:
            values.append([row.get(col) for col in columns])

        cursor.executemany(insert_sql, values)
        conn.commit()
        conn.close()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = WeChatSyncTool()
    window.show()
    sys.exit(app.exec())