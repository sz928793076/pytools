import sys

from PyQt6.QtCore import QUrl, Qt
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QTextEdit, QPushButton, QMessageBox
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEngineCookieStore
from PyQt6.QtNetwork import QNetworkCookie


class CookieExtractor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.login_url = "https://sleye-mobile.lottery.cn/api/RestMsg"
        self.cookies = {}
        self.init_ui()
        self.init_web_engine()

    def init_ui(self):
        self.setWindowTitle("体彩登录 Cookie 提取工具 (手机仿真)")
        self.setGeometry(100, 100, 400, 800)  # 窗口大小模仿手机

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        self.web_view = QWebEngineView()
        layout.addWidget(self.web_view)

        self.cookie_text = QTextEdit()
        self.cookie_text.setReadOnly(True)
        layout.addWidget(self.cookie_text)

        self.copy_btn = QPushButton("复制 Cookie并保存本地")
        self.copy_btn.clicked.connect(self.copy_cookie)
        layout.addWidget(self.copy_btn)

    def init_web_engine(self):
        profile = QWebEngineProfile.defaultProfile()
        cookie_store = profile.cookieStore()

        # 1. 设置手机 UA
        android_ua = (
            "Mozilla/5.0 (Linux; Android 13; Pixel 7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/118.0.0.0 Mobile Safari/537.36"
        )
        profile.setHttpUserAgent(android_ua)

        # 2. 监听 Cookie
        cookie_store.cookieAdded.connect(self.on_cookie_added)
        cookie_store.cookieRemoved.connect(self.on_cookie_removed)

        # 3. 加载页面
        self.web_view.load(QUrl(self.login_url))

        # 4. 页面加载完成后，用 JS 设置视口尺寸
        self.web_view.page().loadFinished.connect(self.set_mobile_viewport)

    def set_mobile_viewport(self, ok):
        """用 JS 设置视口，模拟手机屏幕"""
        if ok:
            js_code = """
                document.body.style.width = '390px';
                document.body.style.height = '844px';
                document.body.style.zoom = '1';
                window.innerWidth = 390;
                window.innerHeight = 844;
                window.devicePixelRatio = 3;
            """
            self.web_view.page().runJavaScript(js_code)

    def on_cookie_added(self, cookie: QNetworkCookie):
        name = cookie.name().data().decode()
        value = cookie.value().data().decode()
        self.cookies[name] = value
        self.update_cookie_display()

    def on_cookie_removed(self, cookie: QNetworkCookie):
        name = cookie.name().data().decode()
        if name in self.cookies:
            del self.cookies[name]
            self.update_cookie_display()

    def update_cookie_display(self):
        cookie_str = "; ".join([f"{k}={v}" for k, v in self.cookies.items()])
        self.cookie_text.setPlainText(cookie_str)
        self.copy_btn.setEnabled(True)

        # 保存到文件
        with open("cookie.txt", "w", encoding="utf-8") as f:
            f.write(cookie_str)

    def copy_cookie(self):
        QApplication.clipboard().setText(self.cookie_text.toPlainText())
        QMessageBox.information(self, "成功", "Cookie 已复制到剪贴板并保存本地")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CookieExtractor()
    window.show()
    sys.exit(app.exec())