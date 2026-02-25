import sys
import subprocess
import re
import winreg
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QMessageBox, QFrame, QTextEdit
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont


class ProxyTool(QMainWindow):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.auto_fetch_ip()

    def init_ui(self):
        self.setWindowTitle("网络代理配置工具 v2.0")
        self.resize(520, 620)
        self.setFixedSize(520, 620)

        # 全局样式表：增加窗口背景色和卡片感
        self.setStyleSheet("""
            QMainWindow { background-color: #f0f2f5; }
            QLabel { color: #333; font-weight: bold; }
            QLineEdit { 
                border: 2px solid #ccc; 
                border-radius: 4px; 
                padding: 5px; 
                background-color: white; 
                selection-background-color: #2196F3;
            }
            QLineEdit:focus { border: 2px solid #2196F3; }
            QTextEdit { 
                border: 1px solid #ccc; 
                border-radius: 4px; 
                background-color: #fafafa; 
                color: #333;
            }
        """)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(25, 20, 25, 20)
        main_layout.setSpacing(15)

        # --- 第一部分：通用参数设置 (卡片样式) ---
        param_group = QFrame()
        param_group.setStyleSheet("QFrame { background-color: white; border-radius: 8px; border: 1px solid #ddd; }")
        param_layout = QVBoxLayout(param_group)

        param_layout.addWidget(QLabel("📍 通用参数设置"))

        ip_layout = QHBoxLayout()
        ip_layout.addWidget(QLabel("代理 IP:"))
        self.ip_input = QLineEdit()
        self.ip_input.setPlaceholderText("正在抓取 WLAN 网关...")
        self.refresh_ip_btn = QPushButton("刷新 IP")
        self.refresh_ip_btn.setFixedWidth(70)
        self.refresh_ip_btn.setStyleSheet("""
            QPushButton { background-color: #e0e0e0; border: 1px solid #999; border-radius: 3px; padding: 4px; }
            QPushButton:hover { background-color: #d0d0d0; }
        """)
        self.refresh_ip_btn.clicked.connect(self.auto_fetch_ip)
        ip_layout.addWidget(self.ip_input)
        ip_layout.addWidget(self.refresh_ip_btn)
        param_layout.addLayout(ip_layout)

        port_layout = QHBoxLayout()
        port_layout.addWidget(QLabel("代理端口:"))
        self.port_input = QLineEdit()
        self.port_input.setText("7890")
        # self.port_input.setText("10808")
        port_layout.addWidget(self.port_input)
        param_layout.addLayout(port_layout)

        main_layout.addWidget(param_group)

        # --- 按钮通用样式函数 ---
        def get_btn_style(color, hover_color):
            return f"""
                QPushButton {{
                    background-color: {color};
                    color: white;
                    border: 1px solid #333;
                    border-radius: 5px;
                    font-weight: bold;
                    font-size: 13px;
                    padding: 10px;
                }}
                QPushButton:hover {{
                    background-color: {hover_color};
                }}
                QPushButton:pressed {{
                    background-color: #222;
                }}
            """

        # --- 第二部分：Git 配置 ---
        git_group = QFrame()
        git_group.setStyleSheet("QFrame { background-color: white; border-radius: 8px; border: 1px solid #ddd; }")
        git_layout = QVBoxLayout(git_group)
        git_layout.addWidget(QLabel("📦 Git 代理配置"))

        git_btn_hbox = QHBoxLayout()
        self.git_set_btn = QPushButton("一键开启 Git 代理")
        self.git_set_btn.setStyleSheet(get_btn_style("#2e7d32", "#1b5e20"))  # 深绿色
        self.git_set_btn.clicked.connect(self.set_git_proxy)

        self.git_clear_btn = QPushButton("清除 Git 代理")
        self.git_clear_btn.setStyleSheet(get_btn_style("#d32f2f", "#b71c1c"))  # 深红色
        self.git_clear_btn.clicked.connect(self.clear_git_proxy)

        git_btn_hbox.addWidget(self.git_set_btn)
        git_btn_hbox.addWidget(self.git_clear_btn)
        git_layout.addLayout(git_btn_hbox)
        main_layout.addWidget(git_group)

        # --- 第三部分：系统配置 ---
        sys_group = QFrame()
        sys_group.setStyleSheet("QFrame { background-color: white; border-radius: 8px; border: 1px solid #ddd; }")
        sys_layout = QVBoxLayout(sys_group)
        sys_layout.addWidget(QLabel("🖥️ Windows 系统代理"))

        sys_btn_hbox = QHBoxLayout()
        self.sys_set_btn = QPushButton("开启系统代理")
        self.sys_set_btn.setStyleSheet(get_btn_style("#ef6c00", "#e65100"))  # 深橙色
        self.sys_set_btn.clicked.connect(self.set_system_proxy)

        self.sys_clear_btn = QPushButton("关闭系统代理")
        self.sys_clear_btn.setStyleSheet(get_btn_style("#4e342e", "#3e2723"))  # 深棕色
        self.sys_clear_btn.clicked.connect(self.clear_system_proxy)

        sys_btn_hbox.addWidget(self.sys_set_btn)
        sys_btn_hbox.addWidget(self.sys_clear_btn)
        sys_layout.addLayout(sys_btn_hbox)
        main_layout.addWidget(sys_group)

        # --- 第四部分：日志区域 ---
        main_layout.addWidget(QLabel("📝 操作日志:"))
        self.log_area = QTextEdit()
        self.log_area.setFixedHeight(120)
        main_layout.addWidget(self.log_area)

        # 底部状态按钮
        self.check_btn = QPushButton("🔍 检查所有代理状态")
        self.check_btn.setFixedHeight(40)
        self.check_btn.setStyleSheet(get_btn_style("#0277bd", "#01579b"))  # 深蓝色
        self.check_btn.clicked.connect(self.check_all_status)
        main_layout.addWidget(self.check_btn)

    # --- 逻辑部分 (保持不变但增加了日志输出) ---
    def auto_fetch_ip(self):
        try:
            result = subprocess.run('ipconfig', capture_output=True, text=True, encoding='gbk', shell=True)
            output = result.stdout
            target_ip, lines = "", output.splitlines()
            is_wlan = False
            for i, line in enumerate(lines):
                if "无线局域网适配器 WLAN" in line or "Wireless LAN adapter WLAN" in line:
                    is_wlan = True
                    continue
                if is_wlan and line.strip() and not line.startswith(" ") and ":" in line and "网关" not in line:
                    is_wlan = False
                if is_wlan and ("默认网关" in line or "Default Gateway" in line):
                    for offset in range(0, 3):
                        if i + offset < len(lines):
                            match = re.search(r'(\d{1,3}(?:\.\d{1,3}){3})', lines[i + offset])
                            if match:
                                target_ip = match.group(1)
                                break
                    if target_ip: break
            if target_ip:
                self.ip_input.setText(target_ip)
                self.log_area.append(f"✅ 自动获取 WLAN 网关成功: {target_ip}")
            else:
                self.log_area.append("❌ 未找到 WLAN 网关，请手动输入。")
        except Exception as e:
            self.log_area.append(f"❌ 获取 IP 错误: {e}")

    def set_git_proxy(self):
        ip, port = self.ip_input.text().strip(), self.port_input.text().strip()
        if not ip: return
        proxy = f"http://{ip}:{port}"
        subprocess.run(f"git config --global http.proxy {proxy}", shell=True)
        subprocess.run(f"git config --global https.proxy {proxy}", shell=True)
        self.log_area.append(f"🚀 Git 代理已开启: {proxy}")
        self.check_all_status()

    def clear_git_proxy(self):
        subprocess.run("git config --global --unset http.proxy", shell=True)
        subprocess.run("git config --global --unset https.proxy", shell=True)
        self.log_area.append("🗑️ Git 代理已清空")
        self.check_all_status()

    def set_system_proxy(self):
        ip, port = self.ip_input.text().strip(), self.port_input.text().strip()
        if not ip: return
        proxy_server = f"{ip}:{port}"
        try:
            xpath = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, xpath, 0, winreg.KEY_WRITE) as key:
                winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 1)
                winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, proxy_server)
                winreg.SetValueEx(key, "ProxyOverride", 0, winreg.REG_SZ, "localhost;127.*;<local>")
            self.log_area.append(f"🌐 系统代理已开启: {proxy_server}")
        except Exception as e:
            self.log_area.append(f"❌ 系统代理设置失败: {e}")
        self.check_all_status()

    def clear_system_proxy(self):
        try:
            xpath = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, xpath, 0, winreg.KEY_WRITE) as key:
                winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 0)
            self.log_area.append("🔒 系统代理已关闭")
        except Exception as e:
            self.log_area.append(f"❌ 系统代理关闭失败: {e}")
        self.check_all_status()

    def check_all_status(self):
        git_res = subprocess.run("git config --global --get http.proxy", capture_output=True, text=True, shell=True)
        git_status = git_res.stdout.strip() or "未配置"

        sys_status = "未知"
        try:
            xpath = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, xpath, 0, winreg.KEY_READ) as key:
                enabled, _ = winreg.QueryValueEx(key, "ProxyEnable")
                server, _ = winreg.QueryValueEx(key, "ProxyServer")
                sys_status = f"开启中 ({server})" if enabled else "已关闭"
        except:
            sys_status = "查询失败"

        self.log_area.append(
            f"\n--- 实时状态检查 ---\nGit 状态: {git_status}\n系统状态: {sys_status}\n------------------")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ProxyTool()
    window.show()
    sys.exit(app.exec())