import sys
import json
import pandas as pd
from datetime import datetime
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
import requests
import pymysql
from sqlalchemy import create_engine
from sqlalchemy import text
import warnings

warnings.filterwarnings('ignore')


class DataExporter(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.cookie = ""

    def initUI(self):
        self.setWindowTitle('数据导出工具')
        self.setGeometry(300, 100, 800, 700)

        # 主布局
        main_layout = QVBoxLayout()

        # 1. Cookie输入
        cookie_group = QGroupBox("Cookie设置")
        cookie_layout = QVBoxLayout()
        self.cookie_input = QTextEdit()
        self.cookie_input.setPlaceholderText("请输入Cookie...")
        self.cookie_input.setMaximumHeight(80)
        cookie_layout.addWidget(QLabel("Cookie:"))
        cookie_layout.addWidget(self.cookie_input)
        cookie_group.setLayout(cookie_layout)

        # 2. URL模板1
        url1_group = QGroupBox("推送详情接口")
        url1_layout = QVBoxLayout()
        self.url1_input = QLineEdit()
        self.url1_input.setText(
            "https://sleye-mobile.lottery.cn/api/v_wechat_send_snapshot_push_detail?triggerTimeBEGIN={startDate}&triggerTimeEND={endDate}")
        url1_layout.addWidget(QLabel("URL模板:"))
        url1_layout.addWidget(self.url1_input)
        url1_group.setLayout(url1_layout)

        # 3. URL模板2
        url2_group = QGroupBox("推送组织接口")
        url2_layout = QVBoxLayout()
        self.url2_input = QLineEdit()
        self.url2_input.setText(
            "https://sleye-mobile.lottery.cn/api/v_wechat_send_snapshot_push_organize?pushTimeBEGIN={startDate}&pushTimeEND={endDate}")
        url2_layout.addWidget(QLabel("URL模板:"))
        url2_layout.addWidget(self.url2_input)
        url2_group.setLayout(url2_layout)

        # 4. 时间选择
        time_group = QGroupBox("时间范围")
        time_layout = QHBoxLayout()
        time_layout.addWidget(QLabel("开始时间:"))
        self.start_date = QDateEdit()
        self.start_date.setDisplayFormat("yyyy-MM-dd")
        self.start_date.setDate(QDate.currentDate().addDays(-7))
        time_layout.addWidget(self.start_date)

        time_layout.addWidget(QLabel("结束时间:"))
        self.end_date = QDateEdit()
        self.end_date.setDisplayFormat("yyyy-MM-dd")
        self.end_date.setDate(QDate.currentDate())
        time_layout.addWidget(self.end_date)

        time_layout.addStretch()
        time_group.setLayout(time_layout)

        # 5. 导出按钮区域
        export_group = QGroupBox("导出数据")
        export_layout = QHBoxLayout()

        self.export_btn1 = QPushButton("导出推送详情数据")
        self.export_btn1.setStyleSheet("background-color: #4CAF50; color: white; padding: 10px;")
        self.export_btn1.clicked.connect(self.export_data1)

        self.export_btn2 = QPushButton("导出推送组织数据")
        self.export_btn2.setStyleSheet("background-color: #2196F3; color: white; padding: 10px;")
        self.export_btn2.clicked.connect(self.export_data2)

        export_layout.addWidget(self.export_btn1)
        export_layout.addWidget(self.export_btn2)
        export_group.setLayout(export_layout)

        # 6. 数据库同步
        db_group = QGroupBox("数据库同步")
        db_layout = QVBoxLayout()

        db_info_layout = QHBoxLayout()
        db_info_layout.addWidget(QLabel("数据库: 127.0.0.1:3308/sleyedb"))
        db_info_layout.addWidget(QLabel("用户: root"))
        db_info_layout.addStretch()

        self.sync_btn = QPushButton("同步数据到数据库并导出结果")
        self.sync_btn.setStyleSheet("background-color: #FF9800; color: white; padding: 10px; font-weight: bold;")
        self.sync_btn.clicked.connect(self.sync_to_database)

        db_layout.addLayout(db_info_layout)
        db_layout.addWidget(self.sync_btn)
        db_group.setLayout(db_layout)

        # 7. 日志区域
        log_group = QGroupBox("操作日志")
        log_layout = QVBoxLayout()
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        log_layout.addWidget(self.log_text)
        log_group.setLayout(log_layout)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)

        # 添加到主布局
        main_layout.addWidget(cookie_group)
        main_layout.addWidget(url1_group)
        main_layout.addWidget(url2_group)
        main_layout.addWidget(time_group)
        main_layout.addWidget(export_group)
        main_layout.addWidget(db_group)
        main_layout.addWidget(self.progress_bar)
        main_layout.addWidget(log_group)

        self.setLayout(main_layout)

    def log_message(self, message):
        """记录日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
        QApplication.processEvents()

    def get_headers(self):
        """获取请求头"""
        cookie_text = self.cookie_input.toPlainText().strip()
        if not cookie_text:
            QMessageBox.warning(self, "警告", "请先输入Cookie！")
            return None

        return {
            'Cookie': cookie_text,
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

    def get_date_range(self):
        """获取时间范围"""
        start = self.start_date.date().toString("yyyy-MM-dd")
        end = self.end_date.date().toString("yyyy-MM-dd")
        return start, end

    def fetch_data(self, url_template):
        """获取接口数据"""
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
        """导出数据到Excel"""
        if not data:
            QMessageBox.warning(self, "警告", "没有数据可以导出！")
            return False

        start_date, end_date = self.get_date_range()
        # 将日期格式化为20251225格式
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
        """导出推送详情数据"""
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(30)
        data = self.fetch_data(self.url1_input.text())
        self.progress_bar.setValue(70)
        if data:
            self.export_to_excel(data, "推送详情")
        self.progress_bar.setValue(100)
        QTimer.singleShot(1000, lambda: self.progress_bar.setVisible(False))

    def export_data2(self):
        """导出推送组织数据"""
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(30)
        data = self.fetch_data(self.url2_input.text())
        self.progress_bar.setValue(70)
        if data:
            self.export_to_excel(data, "推送组织")
        self.progress_bar.setValue(100)
        QTimer.singleShot(1000, lambda: self.progress_bar.setVisible(False))

    def camel_to_snake(self, name):
        """驼峰转下划线"""
        import re
        name = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', name).lower()

    def sync_to_database(self):
        """同步数据到数据库"""
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        headers = self.get_headers()
        if not headers:
            self.progress_bar.setVisible(False)
            return

        try:
            # 连接数据库
            self.log_message("正在连接数据库...")
            self.progress_bar.setValue(10)

            engine = create_engine('mysql+pymysql://root:root@127.0.0.1:3308/sleyedb')

            # 1. 同步wechat_send_business_def表
            self.log_message("开始同步wechat_send_business_def表...")
            self.progress_bar.setValue(20)

            business_def_url = "https://sleye-mobile.lottery.cn/api/wechat_send_business_def"
            response = requests.get(business_def_url, headers=headers, timeout=30)

            if response.status_code == 200:
                business_data = response.json()
                if isinstance(business_data, list):
                    # 转换字段名
                    df_business = pd.DataFrame(business_data)
                    df_business.columns = [self.camel_to_snake(col) for col in df_business.columns]

                    # 清空表并插入数据
                    with engine.begin() as conn:
                        conn.execute(text("TRUNCATE TABLE wechat_send_business_def"))
                    df_business.to_sql('wechat_send_business_def', engine, if_exists='append', index=False)
                    self.log_message(f"wechat_send_business_def表同步完成，{len(business_data)}条记录")
                else:
                    self.log_message("wechat_send_business_def接口返回格式错误")
            else:
                self.log_message(f"wechat_send_business_def接口请求失败: HTTP {response.status_code}")

            self.progress_bar.setValue(40)

            # 2. 同步wechat_send_result表
            self.log_message("开始同步wechat_send_result表...")
            self.progress_bar.setValue(50)

            start_date, end_date = self.get_date_range()
            send_result_url = f"https://sleye-mobile.lottery.cn/api/wechat_send_result?sendTimeBEGIN={start_date}&sendTimeEND={end_date}"

            response = requests.get(send_result_url, headers=headers, timeout=30)

            if response.status_code == 200:
                send_result_data = response.json()
                if isinstance(send_result_data, list):
                    # 转换字段名
                    df_result = pd.DataFrame(send_result_data)
                    df_result.columns = [self.camel_to_snake(col) for col in df_result.columns]

                    # 清空表并插入数据
                    with engine.begin() as conn:
                        conn.execute(text("TRUNCATE TABLE wechat_send_result"))
                    df_result.to_sql('wechat_send_result', engine, if_exists='append', index=False)
                    self.log_message(f"wechat_send_result表同步完成，{len(send_result_data)}条记录")
                else:
                    self.log_message("wechat_send_result接口返回格式错误")
            else:
                self.log_message(f"wechat_send_result接口请求失败: HTTP {response.status_code}")

            self.progress_bar.setValue(70)

            # 3. 执行SQL查询
            self.log_message("正在执行SQL查询...")
            self.progress_bar.setValue(80)

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
                AND wsr.`business_no` = wsbd.`business_no` where wsr.business_type < 10000
            """

            df_result = pd.read_sql(sql, engine)

            self.progress_bar.setValue(90)

            # 4. 导出查询结果
            if not df_result.empty:
                start_str = start_date.replace("-", "")
                end_str = end_date.replace("-", "")
                filename = f"数据库查询结果-{start_str}-{end_str}.xlsx"

                file_path, _ = QFileDialog.getSaveFileName(
                    self, "保存查询结果", filename, "Excel Files (*.xlsx)"
                )

                if file_path:
                    df_result.to_excel(file_path, index=False)
                    self.log_message(f"查询结果已导出到: {file_path}")
                    QMessageBox.information(self, "成功",
                                            f"数据库同步完成！\n查询结果已导出到:\n{file_path}")
            else:
                self.log_message("查询结果为空")
                QMessageBox.information(self, "提示", "数据库同步完成，但查询结果为空")

            self.progress_bar.setValue(100)
            self.log_message("数据库同步任务完成！")

        except pymysql.err.OperationalError as e:
            self.log_message(f"数据库连接失败: {str(e)}")
            QMessageBox.critical(self, "数据库错误",
                                 f"无法连接到数据库:\n{str(e)}\n\n请检查数据库配置和连接状态。")
        except Exception as e:
            self.log_message(f"同步过程中出现错误: {str(e)}")
            QMessageBox.critical(self, "错误", f"同步失败: {str(e)}")
        finally:
            QTimer.singleShot(1000, lambda: self.progress_bar.setVisible(False))


def main():
    app = QApplication(sys.argv)

    # 设置应用程序样式
    app.setStyle('Fusion')

    # 创建并显示窗口
    exporter = DataExporter()
    exporter.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()