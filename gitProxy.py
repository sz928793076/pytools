import sys
import subprocess
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QMessageBox, QFrame
)
from PySide6.QtCore import Qt

class GitProxyTool(QMainWindow):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        # 窗口基础设置
        self.setWindowTitle("Git 代理配置工具")
        self.resize(400, 200)
        self.setFixedSize(400, 200)  # 固定窗口大小，避免拉伸变形

        # 中心控件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 主布局（垂直）
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(40, 40, 40, 40)

        # 1. IP 输入区域
        ip_layout = QHBoxLayout()
        ip_label = QLabel("代理 IP：")
        ip_label.setFixedWidth(60)
        self.ip_input = QLineEdit()
        self.ip_input.setPlaceholderText("如 10.246.7.119")
        ip_layout.addWidget(ip_label)
        ip_layout.addWidget(self.ip_input)
        main_layout.addLayout(ip_layout)

        # 2. 端口输入区域
        port_layout = QHBoxLayout()
        port_label = QLabel("代理端口：")
        port_label.setFixedWidth(60)
        self.port_input = QLineEdit()
        self.port_input.setPlaceholderText("默认 7890")
        self.port_input.setText("7890")  # 默认值
        port_layout.addWidget(port_label)
        port_layout.addWidget(self.port_input)
        main_layout.addLayout(port_layout)

        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        main_layout.addWidget(line)

        # 3. 按钮区域
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(20)

        # 配置代理按钮
        self.set_proxy_btn = QPushButton("一键配置代理")
        self.set_proxy_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 8px;")
        self.set_proxy_btn.clicked.connect(self.set_git_proxy)
        btn_layout.addWidget(self.set_proxy_btn)

        # 清空代理按钮
        self.clear_proxy_btn = QPushButton("一键清空代理")
        self.clear_proxy_btn.setStyleSheet("background-color: #f44336; color: white; padding: 8px;")
        self.clear_proxy_btn.clicked.connect(self.clear_git_proxy)
        btn_layout.addWidget(self.clear_proxy_btn)

        main_layout.addLayout(btn_layout)

    def run_git_command(self, cmd):
        """执行 Git 命令并返回结果"""
        try:
            # 执行命令，捕获输出和错误
            result = subprocess.run(
                cmd,
                shell=True,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding="utf-8"
            )
            return True, result.stdout
        except subprocess.CalledProcessError as e:
            return False, e.stderr
        except Exception as e:
            return False, str(e)

    def set_git_proxy(self):
        """配置 Git 代理"""
        # 获取输入的 IP 和端口
        ip = self.ip_input.text().strip()
        port = self.port_input.text().strip()

        # 校验输入
        if not ip:
            QMessageBox.warning(self, "输入错误", "请填写代理 IP！")
            return
        if not port:
            QMessageBox.warning(self, "输入错误", "请填写代理端口！")
            return
        try:
            port = int(port)
            if port < 1 or port > 65535:
                raise ValueError
        except ValueError:
            QMessageBox.warning(self, "输入错误", "端口必须是 1-65535 之间的数字！")
            return

        # 拼接代理地址
        proxy_addr = f"http://{ip}:{port}"

        # 执行 Git 配置命令
        cmds = [
            f"git config --global http.proxy {proxy_addr}",
            f"git config --global https.proxy {proxy_addr}"
        ]

        # 批量执行命令
        error_msgs = []
        for cmd in cmds:
            success, msg = self.run_git_command(cmd)
            if not success:
                error_msgs.append(msg)

        # 提示结果
        if error_msgs:
            QMessageBox.critical(self, "配置失败", f"配置代理出错：\n{chr(10).join(error_msgs)}")
        else:
            QMessageBox.information(self, "配置成功", f"Git 代理已配置为：\n{proxy_addr}")

    def clear_git_proxy(self):
        """清空 Git 代理"""
        # 执行清空代理的命令
        cmds = [
            "git config --global --unset http.proxy",
            "git config --global --unset https.proxy"
        ]

        # 批量执行命令
        error_msgs = []
        for cmd in cmds:
            success, msg = self.run_git_command(cmd)
            # 允许 "key does not exist" 错误（本来就没有代理时）
            if not success and "key does not exist" not in msg.lower():
                error_msgs.append(msg)

        # 提示结果
        if error_msgs:
            QMessageBox.critical(self, "清空失败", f"清空代理出错：\n{chr(10).join(error_msgs)}")
        else:
            QMessageBox.information(self, "清空成功", "Git 代理已清空！")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = GitProxyTool()
    window.show()
    sys.exit(app.exec())