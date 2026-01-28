import sys
import base64
import json
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QPushButton, QTextEdit, QLabel, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QFont, QAction


class JWTGenerator:
    """JWT生成工具类，对应Java中的JWTUtil"""

    def __init__(self):
        # 与Java代码中相同的密钥（Base64编码）
        self.key = "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAxuNyQuN9FIwK2+jkshAkpkc+gVGnZ0RNQ59PMS457tfBH3tjR6aQXuYox402BNt0pWsm2cYtJPD9ez1KzfZM+YjzoaEXoOqNVeIbNmJtzNjtmc5okEsaoGlop7NPh9a+XGTxvrKd59vf4XcXusDZGscC46YxdjkoyHIqVC4TGy5QTEiFawpXZMA2Q0IZFXbIMfED/mqeY6UFA6+ngxdp+ZophMuLSzCj+vBWmfptgMwrm5L4EU6X2+kvtGylJd5PhFyzVwx3rCGd/wZsc8X2LPMZtTvxEzoD9bMPe5LdC2ouah/QoCQbFPNovmz3RaF78Mk4i8WUg6cNPjduWipDjQIDAQAB"

        # 过期时间（86400分钟 = 60天）
        self.expire_minutes = 86400

        # 预先解码密钥
        self.secret_key = base64.b64decode(self.key)

    def parse_token(self, token: str) -> Optional[dict]:
        """解析JWT Token"""
        if not token or token.strip() == "":
            return None

        try:
            # 解析token
            decoded = jwt.decode(
                token,
                self.secret_key,
                algorithms=['HS256']
            )
            return decoded
        except jwt.ExpiredSignatureError:
            print("Token已过期")
            return None
        except jwt.InvalidTokenError as e:
            print(f"无效的Token: {e}")
            return None
        except Exception as e:
            print(f"解析token失败: {e}")
            return None

    def create_token(self, app_key: int, app_secret: str) -> str:
        """生成JWT Token"""
        # 计算过期时间 - 使用timezone-aware datetime
        expire_time = datetime.now(timezone.utc) + timedelta(minutes=self.expire_minutes)

        # 构建payload
        payload = {
            "appKey": app_key,
            "appSecret": app_secret,
            "exp": expire_time
        }

        # 生成token
        token = jwt.encode(
            payload,
            self.secret_key,
            algorithm='HS256'
        )

        return token

    def get_token(self) -> str:
        """获取固定参数的Token（对应Java中的getToken方法）"""
        return self.create_token(1000581, "odsH8jhjfm3RHQ3ZPlyW0FF5ALZIM")


class TokenGeneratorGUI(QMainWindow):
    """JWT Token生成器GUI"""

    def __init__(self):
        super().__init__()

        # 初始化JWT生成器
        self.jwt_generator = JWTGenerator()

        # 初始化UI
        self.init_ui()

        # 设置窗口属性
        self.setWindowTitle("JWT Token生成器")
        self.setGeometry(100, 100, 800, 600)

    def init_ui(self):
        """初始化用户界面"""
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 创建主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(30, 30, 30, 30)

        # 标题标签
        title_label = QLabel("JWT Token 生成器")
        title_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)

        # 分隔线
        separator = QLabel()
        separator.setFixedHeight(2)
        separator.setStyleSheet("background-color: #ccc;")
        main_layout.addWidget(separator)

        # 说明标签
        desc_label = QLabel(
            "此工具用于生成JWT Token，点击下方按钮生成固定参数的Token"
        )
        desc_label.setFont(QFont("Arial", 10))
        desc_label.setWordWrap(True)
        main_layout.addWidget(desc_label)

        # 参数显示区域
        params_widget = QWidget()
        params_layout = QVBoxLayout(params_widget)
        params_layout.setSpacing(10)

        # 显示固定参数
        params_label = QLabel("固定参数：")
        params_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        params_layout.addWidget(params_label)

        params_text = QLabel(
            f"appKey: 1000581\n"
            f"appSecret: odsH8jhjfm3RHQ3ZPlyW0FF5ALZIM\n"
            f"过期时间: {self.jwt_generator.expire_minutes}分钟"
        )
        params_text.setFont(QFont("Courier", 9))
        params_text.setStyleSheet("background-color: #f5f5f5; padding: 10px; border-radius: 5px;")
        params_text.setWordWrap(True)
        params_layout.addWidget(params_text)

        main_layout.addWidget(params_widget)

        # 按钮区域
        button_widget = QWidget()
        button_layout = QHBoxLayout(button_widget)
        button_layout.setSpacing(20)

        # 生成Token按钮
        generate_btn = QPushButton("生成Token")
        generate_btn.setFont(QFont("Arial", 11))
        generate_btn.setMinimumHeight(40)
        generate_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        """)
        generate_btn.clicked.connect(self.generate_token)
        button_layout.addWidget(generate_btn)

        # 复制按钮
        copy_btn = QPushButton("复制Token")
        copy_btn.setFont(QFont("Arial", 11))
        copy_btn.setMinimumHeight(40)
        copy_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #0b7dda;
            }
            QPushButton:pressed {
                background-color: #0a68b9;
            }
        """)
        copy_btn.clicked.connect(self.copy_token)
        button_layout.addWidget(copy_btn)

        # 清空按钮
        clear_btn = QPushButton("清空")
        clear_btn.setFont(QFont("Arial", 11))
        clear_btn.setMinimumHeight(40)
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
            QPushButton:pressed {
                background-color: #b80c00;
            }
        """)
        clear_btn.clicked.connect(self.clear_output)
        button_layout.addWidget(clear_btn)

        main_layout.addWidget(button_widget)

        # Token显示区域
        token_widget = QWidget()
        token_layout = QVBoxLayout(token_widget)
        token_layout.setSpacing(10)

        # Token标签
        token_label = QLabel("生成的Token：")
        token_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        token_layout.addWidget(token_label)

        # Token显示文本框
        self.token_text = QTextEdit()
        self.token_text.setFont(QFont("Courier", 9))
        self.token_text.setPlaceholderText("点击上方按钮生成Token...")
        self.token_text.setReadOnly(True)
        self.token_text.setMinimumHeight(150)
        self.token_text.setStyleSheet("""
            QTextEdit {
                border: 1px solid #ccc;
                border-radius: 5px;
                padding: 10px;
                background-color: #fafafa;
            }
        """)
        token_layout.addWidget(self.token_text)

        main_layout.addWidget(token_widget)

        # 解析区域
        decode_widget = QWidget()
        decode_layout = QVBoxLayout(decode_widget)
        decode_layout.setSpacing(10)

        # 解析标签
        decode_label = QLabel("Token解析结果：")
        decode_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        decode_layout.addWidget(decode_label)

        # 解析结果显示框
        self.decode_text = QTextEdit()
        self.decode_text.setFont(QFont("Courier", 9))
        self.decode_text.setPlaceholderText("生成Token后自动显示解析结果...")
        self.decode_text.setReadOnly(True)
        self.decode_text.setMinimumHeight(150)
        self.decode_text.setStyleSheet("""
            QTextEdit {
                border: 1px solid #ccc;
                border-radius: 5px;
                padding: 10px;
                background-color: #fafafa;
            }
        """)
        decode_layout.addWidget(self.decode_text)

        main_layout.addWidget(decode_widget)

        # 创建菜单栏
        self.create_menu_bar()

        # 底部状态栏
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("就绪")

    def create_menu_bar(self):
        """创建菜单栏"""
        menubar = self.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu('文件')

        generate_action = QAction('生成Token', self)
        generate_action.triggered.connect(self.generate_token)
        file_menu.addAction(generate_action)

        copy_action = QAction('复制Token', self)
        copy_action.triggered.connect(self.copy_token)
        file_menu.addAction(copy_action)

        file_menu.addSeparator()

        exit_action = QAction('退出', self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # 帮助菜单
        help_menu = menubar.addMenu('帮助')

        about_action = QAction('关于', self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    @pyqtSlot()
    def generate_token(self):
        """生成Token按钮点击事件"""
        try:
            # 生成Token
            token = self.jwt_generator.get_token()

            # 显示Token
            self.token_text.setText(token)

            # 解析Token并显示
            decoded = self.jwt_generator.parse_token(token)
            if decoded:
                # 格式化JSON输出
                formatted_json = json.dumps(decoded, indent=2, ensure_ascii=False)
                self.decode_text.setText(formatted_json)

                # 更新状态栏
                app_key = decoded.get('appKey', 'N/A')
                self.status_bar.showMessage(f"Token生成成功！appKey: {app_key}")
            else:
                self.decode_text.setText("Token解析失败")
                self.status_bar.showMessage("Token生成成功但解析失败")

        except Exception as e:
            error_msg = f"生成Token时出错: {str(e)}"
            QMessageBox.critical(self, "错误", error_msg)
            self.status_bar.showMessage("生成Token失败")

    @pyqtSlot()
    def copy_token(self):
        """复制Token按钮点击事件"""
        token = self.token_text.toPlainText().strip()
        if token:
            # 复制到剪贴板
            clipboard = QApplication.clipboard()
            clipboard.setText(token)

            # 显示提示
            self.status_bar.showMessage("Token已复制到剪贴板", 3000)
        else:
            QMessageBox.warning(self, "警告", "没有可复制的Token内容")

    @pyqtSlot()
    def clear_output(self):
        """清空输出按钮点击事件"""
        self.token_text.clear()
        self.decode_text.clear()
        self.status_bar.showMessage("已清空所有输出", 3000)

    @pyqtSlot()
    def show_about(self):
        """显示关于对话框"""
        about_text = """
        JWT Token生成器

        版本: 1.0
        作者: 根据Java代码转换

        功能:
        1. 生成JWT Token
        2. 自动解析Token内容
        3. 复制Token到剪贴板

        基于Java JWT工具类转换而来。
        """

        QMessageBox.about(self, "关于", about_text)


def main():
    """主函数"""
    app = QApplication(sys.argv)

    # 设置应用程序样式
    app.setStyle('Fusion')

    # 创建并显示主窗口
    window = TokenGeneratorGUI()
    window.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()