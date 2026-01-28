import sys
import random
import requests
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QToolBar, QPushButton,
    QFileDialog, QMessageBox
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import QUrl
import pandas as pd


class WeWorkBrowser(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("企业微信数据导出工具（PyQt6）")
        self.setGeometry(100, 100, 1200, 800)

        # 存储数据的变量
        self.cookies = {}
        self.app_id = None
        self.user_data = []

        # 先创建浏览器视图
        self.browser = QWebEngineView()
        self.browser.page().profile().cookieStore().cookieAdded.connect(self.on_cookie_added)
        self.browser.setUrl(QUrl("https://work.weixin.qq.com/wework_admin/loginpage_wx"))

        # 创建工具栏
        self.create_toolbar()

        # 设置中心部件
        self.setCentralWidget(self.browser)

    def create_toolbar(self):
        """创建工具栏（使用QPushButton）"""
        toolbar = QToolBar("工具")
        self.addToolBar(toolbar)

        # 获取Cookie按钮
        btn_get_cookie = QPushButton("获取Cookie")
        btn_get_cookie.clicked.connect(self.get_cookies)
        toolbar.addWidget(btn_get_cookie)

        # 获取App ID按钮
        btn_get_appid = QPushButton("获取App ID")
        btn_get_appid.clicked.connect(self.get_app_id)
        toolbar.addWidget(btn_get_appid)

        # 调用API按钮
        btn_call_api = QPushButton("调用API并导出")
        btn_call_api.clicked.connect(self.call_api_and_export)
        toolbar.addWidget(btn_call_api)

        # 刷新按钮
        btn_refresh = QPushButton("刷新")
        btn_refresh.clicked.connect(self.browser.reload)
        toolbar.addWidget(btn_refresh)

        # 后退按钮
        btn_back = QPushButton("后退")
        btn_back.clicked.connect(self.browser.back)
        toolbar.addWidget(btn_back)

        # 前进按钮
        btn_forward = QPushButton("前进")
        btn_forward.clicked.connect(self.browser.forward)
        toolbar.addWidget(btn_forward)

    def on_cookie_added(self, cookie):
        """捕获cookie"""
        name = cookie.name().data().decode('utf-8')
        value = cookie.value().data().decode('utf-8')
        self.cookies[name] = value

    def get_cookies(self):
        """获取并显示当前cookie"""
        if self.cookies:
            QMessageBox.information(self, "成功", f"已获取 {len(self.cookies)} 个 Cookie")
            print("获取的 Cookie:", self.cookies)
        else:
            QMessageBox.warning(self, "警告", "尚未获取到 Cookie，请先登录")

    def get_app_id(self):
        """从当前URL提取app_id"""
        current_url = self.browser.url().toString()
        print("当前 URL:", current_url)

        if "modApiApp/" in current_url:
            try:
                parts = current_url.split("modApiApp/")
                if len(parts) > 1:
                    self.app_id = parts[1].split("#")[0].split("?")[0]
                    QMessageBox.information(self, "成功", f"已提取 App ID: {self.app_id}")
                    print("提取的 App ID:", self.app_id)
                    return
            except Exception as e:
                print("提取 App ID 失败:", e)

        QMessageBox.warning(self, "警告", "未能从当前 URL 提取 App ID，请确保在自建应用页面")

    def call_api_and_export(self):
        """调用API并导出数据"""
        if not self.cookies:
            QMessageBox.warning(self, "警告", "请先获取 Cookie")
            return

        if not self.app_id:
            QMessageBox.warning(self, "警告", "请先获取 App ID")
            return

        random_num = random.random()
        api_url = (
            f"https://work.weixin.qq.com/wework_admin/apps/getOpenApiApp"
            f"?lang=zh_CN&f=json&ajax=1&timeZoneInfo%5Bzone_offset%5D=-8"
            f"&random={random_num}&app_id={self.app_id}&bind_mini_program=false"
        )

        try:
            response = requests.get(
                api_url,
                cookies=self.cookies,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                                  'AppleWebKit/537.36 (KHTML, like Gecko) '
                                  'Chrome/114.0.0.0 Safari/537.36',
                    'Referer': 'https://work.weixin.qq.com/wework_admin/frame',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                self.process_api_response(data)

                filename, _ = QFileDialog.getSaveFileName(
                    self, "保存文件",
                    f"企业微信数据_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    "Excel 文件 (*.xlsx)"
                )

                if filename:
                    self.export_to_excel(filename)
                    QMessageBox.information(self, "成功", f"数据已导出到: {filename}")
            else:
                QMessageBox.critical(self, "错误", f"API 请求失败，状态码: {response.status_code}")
                print("API 响应:", response.text)

        except Exception as e:
            QMessageBox.critical(self, "错误", f"请求 API 时出错: {str(e)}")
            print("API 请求错误:", e)

    def process_api_response(self, data):
        """处理API响应数据"""
        self.user_data = []

        if 'data' in data and 'app_perm' in data['data'] and 'vids' in data['data']['app_perm']:
            for vid in data['data']['app_perm']['vids']:
                user_info = {
                    'name': vid.get('name', ''),
                    'mobile': vid.get('mobile', ''),
                    '部门': vid.get('mainparty_name', '')
                }

                if 'wxqy_userid' in vid:
                    user_info['userid'] = vid['wxqy_userid']
                else:
                    user_info['userid'] = vid.get('acctid', '')

                self.user_data.append(user_info)

        print(f"处理完成，共提取 {len(self.user_data)} 条用户数据")

    def export_to_excel(self, filename):
        """导出数据到Excel"""
        if self.user_data:
            df = pd.DataFrame(self.user_data)
            df.to_excel(filename, index=False)
            print(f"数据已导出到: {filename}")
        else:
            QMessageBox.warning(self, "警告", "没有可导出的数据")


def main():
    app = QApplication(sys.argv)
    window = WeWorkBrowser()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()