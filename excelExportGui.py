import os
import re
import sys
import subprocess
from datetime import datetime
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QLineEdit,
    QPushButton, QTextEdit, QGridLayout, QVBoxLayout,
    QHBoxLayout, QGroupBox, QMessageBox, QSpinBox, QComboBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

# ================== 固定配置（核心修改：新增EXPORT_DIR）==================
SHEET_MAIN = "checklist模板"  # 主sheet名称
SHEET_AOPS = "AOPS变更编排"  # AOPS sheet名称
# 单元格地址配置
CELL_CONFIG = {
    "change_title": "B5", "start_time": "H5", "work_order": "C6",
    "ref_time": "F20", "sql_statement": "C29", "aops_desc_have_script": "C32",
    "aops_desc_no_script": "C27", "aops_time": "B4", "aops_order": "C4"
}
# AOPS自动脚本单元格配置（B5、C5）
AOPS_AUTO_CELLS = {"time": "B5", "order": "C5"}
# 程序根目录 + 模板目录(mnt) + 输出目录(export)（自动识别，无需手动配置）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MNT_DIR = os.path.join(BASE_DIR, "mnt")  # 模板文件存放目录
EXPORT_DIR = os.path.join(BASE_DIR, "export")  # 输出文件存放目录（新增）


class ExcelUpdateGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.selected_template = ""  # 选中的模板文件路径
        self.init_ui()  # 初始化界面
        self.load_mnt_files()  # 加载mnt文件夹下的文件到下拉框

    def init_ui(self):
        # 窗口基础设置
        self.setWindowTitle("Excel变更清单更新工具 V1.6（export输出+自动打开）")
        self.setMinimumSize(900, 900)  # 适配布局高度
        self.center_window()  # 窗口居中

        # 全局字体设置
        self.font_normal = QFont("Microsoft YaHei", 10)
        self.font_title = QFont("Microsoft YaHei", 12, QFont.Bold)
        self.font_log = QFont("Consolas", 9)

        # 中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(30, 30, 30, 30)

        # 1. mnt文件选择组（下拉框替代文件选择按钮）
        self.mnt_group = self.create_mnt_file_group()
        # 2. 解析功能组
        parse_group = self.create_parse_group()
        # 3. 参数输入组（保留双脚本选项）
        param_group = self.create_param_group()
        # 4. 操作按钮组
        btn_group = self.create_button_group()
        # 5. 日志输出组
        log_group = self.create_log_group()

        # 添加所有组到主布局
        main_layout.addWidget(self.mnt_group)
        main_layout.addWidget(parse_group)
        main_layout.addWidget(param_group)
        main_layout.addWidget(btn_group)
        main_layout.addWidget(log_group, stretch=1)

        # 设置全局样式
        self.set_style_sheet()

    def center_window(self):
        """窗口居中显示"""
        qr = self.frameGeometry()
        cp = QApplication.primaryScreen().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

    def create_mnt_file_group(self):
        """创建mnt文件选择组（下拉框+刷新按钮）"""
        group = QGroupBox("模板文件选择（自动加载当前目录/mnt下文件）")
        group.setFont(self.font_title)
        layout = QHBoxLayout()
        layout.setSpacing(15)

        # 标签
        label = QLabel("选择模板：")
        label.setFont(self.font_normal)
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)

        # 模板文件下拉框
        self.mnt_file_combo = QComboBox()
        self.mnt_file_combo.setFont(self.font_normal)
        self.mnt_file_combo.setMinimumHeight(35)
        self.mnt_file_combo.setMinimumWidth(400)
        self.mnt_file_combo.setPlaceholderText("")
        # 绑定下拉框选择事件
        self.mnt_file_combo.currentTextChanged.connect(self.on_mnt_file_selected)
        layout.addWidget(self.mnt_file_combo, stretch=1)

        # 刷新按钮（手动刷新mnt文件夹）
        self.refresh_mnt_btn = QPushButton("刷新列表")
        self.refresh_mnt_btn.setFont(self.font_normal)
        self.refresh_mnt_btn.setMinimumHeight(35)
        self.refresh_mnt_btn.setMinimumWidth(100)
        self.refresh_mnt_btn.clicked.connect(self.load_mnt_files)
        layout.addWidget(self.refresh_mnt_btn)

        group.setLayout(layout)
        return group

    def load_mnt_files(self):
        """加载mnt文件夹下所有Excel文件到下拉框，自动过滤非Excel文件"""
        try:
            # 清空下拉框原有内容
            self.mnt_file_combo.clear()
            self.selected_template = ""

            # 检查mnt文件夹是否存在，不存在则创建
            if not os.path.exists(MNT_DIR):
                os.makedirs(MNT_DIR)
                self.log(f"ℹ mnt模板文件夹不存在，已自动创建：{MNT_DIR}", "info")
                QMessageBox.information(self, "提示",
                                        f"未检测到mnt模板文件夹，已自动在程序目录创建：\n{MNT_DIR}\n请将Excel模板放入该文件夹后刷新！")
                return

            # 遍历mnt文件夹，获取所有Excel文件
            excel_suffix = [".xlsx", ".xlsm", ".xls", ".xltx", ".xltm"]
            all_files = [f for f in os.listdir(MNT_DIR)
                         if os.path.isfile(os.path.join(MNT_DIR, f))
                         and os.path.splitext(f)[1].lower() in excel_suffix]

            if not all_files:
                self.mnt_file_combo.addItem("mnt文件夹内无Excel模板文件，请放入后刷新")
                self.log(f"ℹ mnt模板文件夹内无Excel文件：{MNT_DIR}", "info")
                return

            # 将Excel文件添加到下拉框
            self.mnt_file_combo.addItems(sorted(all_files))
            self.log(f"✅ 成功加载mnt文件夹{len(all_files)}个Excel模板文件", "success")

        except Exception as e:
            error_info = f"加载mnt模板文件失败：{str(e)}"
            self.mnt_file_combo.addItem(f"加载失败：{error_info[:20]}...")
            self.log(f"❌ {error_info}", "error")
            QMessageBox.critical(self, "错误", f"加载mnt模板文件夹文件失败：\n{str(e)}")

    def on_mnt_file_selected(self, file_name):
        """下拉框选择事件：更新选中的模板文件路径"""
        if "无Excel模板文件" in file_name or "加载失败" in file_name:
            self.selected_template = ""
            return
        self.selected_template = os.path.join(MNT_DIR, file_name)
        self.log(f"📂 已选中模板文件：{self.selected_template}", "info")

    def create_parse_group(self):
        """创建解析功能组"""
        group = QGroupBox("一键解析参数（非必填）")
        group.setFont(self.font_title)
        layout = QVBoxLayout()
        layout.setSpacing(10)

        self.parse_text = QTextEdit()
        self.parse_text.setFont(self.font_normal)
        self.parse_text.setMinimumHeight(100)
        self.parse_text.setPlaceholderText(
            "请粘贴待解析的文本，格式如下：\n变更工单号\n变更标题\n实施时间（yyyy-mm-ddTHH:MM）\n参考用时（MM:SS）\nAOPS发布单\n\n示例：\nCM20260122105841291914\n统一业务监控系统V26.01.01\n2026-01-29T22:30\n00:20\nR2026012913430962719811")
        self.parse_text.setStyleSheet(
            "border: 1px solid #E0E0E0; border-radius: 6px; padding: 10px; background: #F8F8F8;")

        self.parse_btn = QPushButton("一键解析并填充")
        self.parse_btn.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
        self.parse_btn.setMinimumHeight(35)
        self.parse_btn.clicked.connect(self.parse_params)

        layout.addWidget(self.parse_text)
        layout.addWidget(self.parse_btn, alignment=Qt.AlignRight)
        group.setLayout(layout)
        return group

    def create_param_group(self):
        """创建参数输入组（保留双脚本下拉选项）"""
        group = QGroupBox("更新参数输入（解析后可编辑）")
        group.setFont(self.font_title)
        layout = QGridLayout()
        layout.setSpacing(15)
        layout.setHorizontalSpacing(20)

        # 定义输入框标签和对应组件
        self.input_widgets = {}
        params = [
            ("变更标题：", "change_title", QLineEdit, {"placeholder": "例：统一业务监控系统V26.01.02"}),
            ("实施时间：", "start_time", QLineEdit, {"placeholder": "例：开始实施时间：2026-01-30 22:30"}),
            ("变更工单号：", "work_order", QLineEdit, {"placeholder": "例：CM20260130105841291914"}),
            ("参考用时(分钟)：", "ref_time", QSpinBox, {"min": 1, "max": 999, "value": 20}),
            ("AOPS发布单：", "aops_order", QLineEdit, {"placeholder": "例：R2026012913430962719899"}),
            ("是否含脚本：", "have_script", QComboBox, {"options": ["是", "否"], "default": 0}),
            ("是否含自动脚本：", "have_auto_script", QComboBox, {"options": ["是", "否"], "default": 1})
        ]

        # 逐个添加参数输入项
        for row, (label_text, key, widget_cls, kwargs) in enumerate(params):
            label = QLabel(label_text)
            label.setFont(self.font_normal)
            label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            layout.addWidget(label, row, 0)

            widget = widget_cls()
            widget.setFont(self.font_normal)
            widget.setMinimumHeight(35)
            widget.setStyleSheet("border: 1px solid #E0E0E0; border-radius: 6px; padding: 0 10px;")
            if widget_cls == QLineEdit:
                widget.setPlaceholderText(kwargs["placeholder"])
            elif widget_cls == QSpinBox:
                widget.setMinimum(kwargs["min"])
                widget.setMaximum(kwargs["max"])
                widget.setValue(kwargs["value"])
                widget.setButtonSymbols(QSpinBox.NoButtons)
            elif widget_cls == QComboBox:
                widget.addItems(kwargs["options"])
                widget.setCurrentIndex(kwargs["default"])
                widget.setEditable(False)
            self.input_widgets[key] = widget
            layout.addWidget(widget, row, 1, 1, 3)

        group.setLayout(layout)
        return group

    def create_button_group(self):
        """创建操作按钮组"""
        group = QWidget()
        layout = QHBoxLayout()
        layout.setSpacing(20)

        self.run_btn = QPushButton("执行更新")
        self.run_btn.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))
        self.run_btn.setMinimumSize(120, 40)
        self.run_btn.clicked.connect(self.run_excel_update)

        self.clear_log_btn = QPushButton("清空日志")
        self.clear_log_btn.setFont(self.font_normal)
        self.clear_log_btn.setMinimumSize(100, 40)
        self.clear_log_btn.clicked.connect(self.clear_log)

        layout.addWidget(self.run_btn, alignment=Qt.AlignLeft)
        layout.addWidget(self.clear_log_btn, alignment=Qt.AlignRight)
        group.setLayout(layout)
        return group

    def create_log_group(self):
        """创建日志输出组"""
        group = QGroupBox("操作日志")
        group.setFont(self.font_title)
        layout = QVBoxLayout()

        self.log_text = QTextEdit()
        self.log_text.setFont(self.font_log)
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet(
            "border: 1px solid #E0E0E0; border-radius: 6px; padding: 10px; background: #FDFDFD;")
        self.log(f"✅ 程序已就绪（V1.6），模板目录：{MNT_DIR} | 输出目录：{EXPORT_DIR}", "success")

        layout.addWidget(self.log_text)
        group.setLayout(layout)
        return group

    def set_style_sheet(self):
        """设置全局样式表（兼容所有组件）"""
        self.setStyleSheet("""
            QMainWindow {background-color: #FFFFFF;}
            QGroupBox {
                border: 1px solid #E0E0E0; border-radius: 8px;
                margin-top: 10px; padding-top: 15px;
                background-color: #FAFAFA;
            }
            QGroupBox::title {
                subcontrol-origin: margin; left: 15px;
                padding: 0 10px; color: #2196F3;
            }
            QPushButton {
                border: none; border-radius: 8px;
                background-color: #2196F3; color: white;
            }
            QPushButton:hover {background-color: #1976D2;}
            QPushButton:pressed {background-color: #1565C0;}
            QPushButton#clear_log_btn {background-color: #FF9800;}
            QPushButton#clear_log_btn:hover {background-color: #FB8C00;}
            QPushButton#clear_log_btn:pressed {background-color: #FFC107;}
            QPushButton#parse_btn {
                background-color: #4CAF50; min-width: 120px;
            }
            QPushButton#parse_btn:hover {background-color: #388E3C;}
            QPushButton#parse_btn:pressed {background-color: #2E7D32;}
            QPushButton#refresh_mnt_btn {
                background-color: #FFC107; min-width: 100px;
            }
            QPushButton#refresh_mnt_btn:hover {background-color: #FFB300;}
            QPushButton#refresh_mnt_btn:pressed {background-color: #FFA000;}
            QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QTextEdit:focus {
                border: 2px solid #2196F3; outline: none;
            }
            QComboBox {
                border: 1px solid #E0E0E0; border-radius: 6px;
                padding: 0 10px; background: white; color: #333333;
            }
            QComboBox::drop-down {border: none; padding-right: 10px;}
            QTextEdit {border: 1px solid #E0E0E0; border-radius: 6px; color: #333333;}
            QLabel {color: #333333;}
            QTextEdit#log_text {color: #333333; font-family: Consolas;}
        """)
        self.clear_log_btn.setObjectName("clear_log_btn")
        self.parse_btn.setObjectName("parse_btn")
        self.refresh_mnt_btn.setObjectName("refresh_mnt_btn")
        self.log_text.setObjectName("log_text")

    def log(self, message, level="info"):
        """日志输出（带颜色和时间）"""
        current_time = datetime.now().strftime("%H:%M:%S")
        color_map = {
            "info": "#333333", "success": "#4CAF50",
            "warning": "#FF9800", "error": "#F44336"
        }
        color = color_map.get(level, "#333333")
        log_msg = f'<span style="color:{color}">[{current_time}] {message}</span><br>'
        self.log_text.insertHtml(log_msg)
        self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())

    def clear_log(self):
        """清空日志"""
        self.log_text.clear()
        self.log(f"✅ 日志已清空，程序就绪（V1.6），模板目录：{MNT_DIR} | 输出目录：{EXPORT_DIR}", "success")

    def open_folder(self, folder_path):
        """跨平台打开文件夹（兼容Windows/Mac/Linux）"""
        try:
            # 检查文件夹是否存在，不存在则创建
            if not os.path.exists(folder_path):
                os.makedirs(folder_path)
                self.log(f"ℹ 文件夹不存在，已自动创建：{folder_path}", "info")
            if sys.platform == "win32":
                # Windows系统
                os.startfile(folder_path)
            elif sys.platform == "darwin":
                # Mac系统
                subprocess.run(["open", folder_path], check=True, capture_output=True)
            else:
                # Linux系统
                subprocess.run(["xdg-open", folder_path], check=True, capture_output=True)
            self.log(f"✅ 已自动打开文件夹：{folder_path}", "success")
        except Exception as e:
            error_info = f"打开文件夹失败：{str(e)}"
            self.log(f"⚠ {error_info}", "warning")
            QMessageBox.warning(self, "提示",
                                f"自动打开文件夹失败，请手动前往：\n{folder_path}\n\n错误信息：{error_info[:50]}...")

    def parse_params(self):
        """一键解析参数（修复参考用时解析逻辑）"""
        try:
            raw_text = self.parse_text.toPlainText().strip()
            if not raw_text:
                QMessageBox.warning(self, "提示", "解析框不能为空，请粘贴待解析的文本！")
                return
            lines = [line.strip() for line in raw_text.split("\n") if line.strip()]
            if len(lines) != 5:
                raise ValueError(f"解析文本行数错误，需5行，当前{len(lines)}行！")

            work_order, change_title, time_str, duration_str, aops_order = lines

            # 解析实施时间：2026-01-29T22:30 → 开始实施时间：2026-01-29 22:30
            if "T" not in time_str:
                raise ValueError(f"实施时间格式错误，需包含T（示例：2026-01-29T22:30）")
            parse_time = time_str.replace("T", " ")
            start_time = f"开始实施时间：{parse_time}"

            # 修复参考用时解析逻辑：MM:SS → 总秒数作为分钟数（00:20=20、01:30=90）
            if ":" not in duration_str or len(duration_str.split(":")) != 2:
                raise ValueError(f"参考用时格式错误，需MM:SS（示例：00:20、01:30）")
            min_part, sec_part = duration_str.split(":")
            if not min_part.isdigit() or not sec_part.isdigit():
                raise ValueError(f"参考用时包含非数字字符，仅支持MM:SS数字格式")
            min_int, sec_int = int(min_part), int(sec_part)
            total_seconds = min_int * 60 + sec_int
            total_min = max(total_seconds, 1)  # 最小1分钟

            # 基础格式校验
            if not re.search(r'V\d+\.\d+\.\d+', change_title):
                raise ValueError(f"变更标题无有效版本号（格式如V26.01.01）")
            if not work_order.startswith("CM"):
                self.log(f"⚠ 变更工单号未以CM开头，可能格式错误：{work_order}", "warning")
            if not aops_order.startswith("R"):
                self.log(f"⚠ AOPS发布单未以R开头，可能格式错误：{aops_order}", "warning")

            # 自动填充到对应输入框
            self.input_widgets["work_order"].setText(work_order)
            self.input_widgets["change_title"].setText(change_title)
            self.input_widgets["start_time"].setText(start_time)
            self.input_widgets["ref_time"].setValue(total_min)
            self.input_widgets["aops_order"].setText(aops_order)

            self.log(f"✅ 解析成功！参考用时：{duration_str}→{total_min}分钟", "success")
            QMessageBox.information(
                self, "解析成功",
                f"参数解析完成，已自动填充！\n\n"
                f"变更工单号：{work_order}\n变更标题：{change_title}\n"
                f"实施时间：{start_time}\n参考用时：{duration_str}→{total_min}分钟\n"
                f"AOPS发布单：{aops_order}\n\n可手动编辑修正！",
                QMessageBox.Ok
            )

        except Exception as e:
            error_info = f"{type(e).__name__}：{str(e)}"
            self.log(f"❌ 解析失败：{error_info}", "error")
            QMessageBox.critical(
                self, "解析失败",
                f"参数解析出错，请检查格式！\n\n{error_info}\n\n"
                f"请按格式粘贴：\n变更工单号\n变更标题\n实施时间（yyyy-mm-ddTHH:MM）\n参考用时（MM:SS）\nAOPS发布单",
                QMessageBox.Ok
            )

    def get_input_params(self):
        """获取所有输入参数并校验"""
        have_script = self.input_widgets["have_script"].currentText() == "是"
        have_auto_script = self.input_widgets["have_auto_script"].currentText() == "是"

        params = {
            "change_title": self.input_widgets["change_title"].text().strip(),
            "start_time": self.input_widgets["start_time"].text().strip(),
            "work_order": self.input_widgets["work_order"].text().strip(),
            "ref_time": self.input_widgets["ref_time"].value(),
            "aops_order": self.input_widgets["aops_order"].text().strip(),
            "have_script": have_script,
            "have_auto_script": have_auto_script
        }
        # 校验必填参数
        required = ["change_title", "start_time", "work_order", "aops_order"]
        for key in required:
            if not params[key]:
                raise ValueError(f"【{key.replace('_', ' ')}】为必填项，请输入！")
        # 校验版本号和时间格式
        if not re.search(r'V\d+\.\d+\.\d+', params["change_title"]):
            raise ValueError("变更标题中未找到有效版本号（格式如：V26.01.02）")
        if not re.search(r'(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2})', params["start_time"]):
            raise ValueError("实施时间格式错误（示例：开始实施时间：2026-01-30 22:30）")
        return params

    def safe_set_cell_value(self, sheet, cell_addr, value):
        """安全设置单元格值（处理合并单元格）"""
        for merged_range in sheet.merged_cells.ranges:
            if cell_addr in merged_range:
                start_row = merged_range.min_row
                start_col = merged_range.min_col
                sheet.cell(row=start_row, column=start_col).value = value
                self.log(
                    f"✓ 已修改合并区域 [{merged_range}] 起始单元格 {get_column_letter(start_col)}{start_row} = {str(value)[:50]}...",
                    "success")
                return
        sheet[cell_addr] = value
        self.log(f"✓ 已修改单元格 {cell_addr} = {str(value)[:50]}...", "success")

    def generate_sql_statement(self, params):
        """动态生成SQL语句"""
        date_match = re.search(r'(\d{4})-(\d{2})-(\d{2})', params["start_time"])
        if not date_match:
            raise ValueError("实施时间解析日期失败！")
        year, month, day = date_match.groups()
        sql_id = f"{year}{month}{day}_1"

        ver_match = re.search(r'V\d+\.\d+\.\d+', params["change_title"])
        db_version = ver_match.group()

        month_match = re.search(r'V\d+\.(\d{2})\.', params["change_title"])
        month = int(month_match.group(1))
        month_desc = f"{month}月迭代版本"

        sql = (
            f"INSERT INTO sleyedb.log_db_version (id, viminal_no, viminal_name, app_version, db_version, descs, developer, create_time) "
            f"VALUES ('{sql_id}', '{params["work_order"]}', '{params["change_title"]}', '', '{db_version}', '{month_desc}', '李立伟', NOW());"
        )
        return sql

    def parse_aops_time(self, start_time_str):
        """解析实施时间为AOPS需要的格式：2026/1/30 22:30:00"""
        time_match = re.search(r'(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2})', start_time_str)
        if not time_match:
            raise ValueError("实施时间解析失败！")
        year, month, day, hour, minute = time_match.groups()
        return f"{year}/{int(month)}/{int(day)} {hour}:{minute}:00"

    def run_excel_update(self):
        """执行Excel更新主逻辑（核心修改：输出至export文件夹+自动打开export）"""
        self.run_btn.setEnabled(False)
        self.run_btn.setText("执行中...")
        try:
            # 校验mnt模板是否选中
            if not self.selected_template or not os.path.exists(self.selected_template):
                raise ValueError("请先从下拉框选择有效的Excel模板文件（mnt文件夹内）！")
            # 获取并校验所有输入参数
            params = self.get_input_params()
            self.log(
                f"📋 输入参数校验通过，模式：含脚本={params['have_script']} | 含自动脚本={params['have_auto_script']}",
                "info")
            self.log(f"🔧 开始处理模板：{os.path.basename(self.selected_template)}", "info")

            # 核心修改：检查并创建export输出文件夹（不存在则自动创建）
            if not os.path.exists(EXPORT_DIR):
                os.makedirs(EXPORT_DIR)
                self.log(f"ℹ export输出文件夹不存在，已自动创建：{EXPORT_DIR}", "info")

            # 新文件命名规则 - checklist-{变更标题}版本变更实施.xlsx（保存至export文件夹）
            new_file_name = f"checklist-{params['change_title']}版本变更实施.xlsx"
            new_file = os.path.join(EXPORT_DIR, new_file_name)  # 输出路径改为export
            self.log(f"📄 新文件命名：{new_file_name}（将保存至export文件夹）", "info")

            # 加载Excel工作簿
            wb = load_workbook(self.selected_template, read_only=False, data_only=False)

            # 处理主sheet：checklist模板
            if SHEET_MAIN not in wb.sheetnames:
                raise ValueError(f"主工作表「{SHEET_MAIN}」不存在！")
            sheet_main = wb[SHEET_MAIN]
            self.log(f"📑 开始处理主工作表：{SHEET_MAIN}", "info")

            # 基础字段赋值
            self.safe_set_cell_value(sheet_main, CELL_CONFIG["change_title"], params["change_title"])
            self.safe_set_cell_value(sheet_main, CELL_CONFIG["start_time"], params["start_time"])
            self.safe_set_cell_value(sheet_main, CELL_CONFIG["work_order"], params["work_order"])
            ref_time_val = f"{params['ref_time']}分钟"
            self.safe_set_cell_value(sheet_main, CELL_CONFIG["ref_time"], ref_time_val)

            # 原是否含脚本逻辑
            if params["have_script"]:
                sql_val = self.generate_sql_statement(params)
                self.safe_set_cell_value(sheet_main, CELL_CONFIG["sql_statement"], sql_val)
            else:
                self.log(f"ℹ 不含脚本，跳过{CELL_CONFIG['sql_statement']} SQL语句生成", "warning")

            # AOPS说明文本单元格切换
            aops_desc_cell = CELL_CONFIG["aops_desc_have_script"] if params["have_script"] else CELL_CONFIG[
                "aops_desc_no_script"]
            aops_desc_val = (
                f"在AOPS中执行发布单为{params['aops_order']}的变更，流水线类型：详见标签页AOPS变更编排\n"
                "结果信息查看：（变更计划实际执行结果为部署管理-部署流水线中实际执行）\n"
                "1、在变更计划执行列表中，操作列，点击跳转详情，查看流水线实际执行情况；\n"
                "2、部署管理-部署流水线列表，查找对应的流水线运行情况，打开节点查看详细日志"
            )
            self.safe_set_cell_value(sheet_main, aops_desc_cell, aops_desc_val)
            self.log(f"ℹ AOPS说明已写入单元格：{aops_desc_cell}", "info")

            # 处理AOPS变更编排sheet
            if SHEET_AOPS not in wb.sheetnames:
                raise ValueError(f"AOPS工作表「{SHEET_AOPS}」不存在！")
            sheet_aops = wb[SHEET_AOPS]
            self.log(f"📑 开始处理AOPS工作表：{SHEET_AOPS}", "info")

            # 设置B4、C4
            aops_time_val = self.parse_aops_time(params["start_time"])
            self.safe_set_cell_value(sheet_aops, CELL_CONFIG["aops_time"], aops_time_val)
            self.safe_set_cell_value(sheet_aops, CELL_CONFIG["aops_order"], params["aops_order"])

            # 是否含自动脚本判断（B5=B4、C5=C4）
            if params["have_auto_script"]:
                self.log(f"ℹ 含自动脚本，执行AOPS工作表B5=B4、C5=C4赋值", "info")
                b4_value = sheet_aops[CELL_CONFIG["aops_time"]].value
                c4_value = sheet_aops[CELL_CONFIG["aops_order"]].value
                self.safe_set_cell_value(sheet_aops, AOPS_AUTO_CELLS["time"], b4_value)
                self.safe_set_cell_value(sheet_aops, AOPS_AUTO_CELLS["order"], c4_value)
            else:
                self.log(f"ℹ 不含自动脚本，AOPS工作表保持原有逻辑", "info")

            # 保存新Excel文件（至export文件夹）
            self.log(f"💾 正在保存新文件到export文件夹：{new_file_name}", "info")
            wb.save(new_file)
            wb.close()

            # 核心修改：生成成功后自动打开export文件夹（而非原mnt）
            self.open_folder(EXPORT_DIR)

            # 操作成功提示
            self.log(f"✅ 操作完成！新文件已生成至export文件夹：{new_file}", "success")
            QMessageBox.information(
                self, "操作成功",
                f"Excel更新完成！\n\n"
                f"模式：含脚本={params['have_script']} | 含自动脚本={params['have_auto_script']}\n\n"
                f"新文件路径：\n{new_file}\n\n已自动打开export文件夹，可直接查看！",
                QMessageBox.Ok
            )

        except Exception as e:
            # 全局异常捕获
            error_info = f"{type(e).__name__}：{str(e)}"
            self.log(f"❌ 操作失败：{error_info}", "error")
            QMessageBox.critical(
                self, "操作失败",
                f"更新过程中出现错误：\n\n{error_info}\n\n请查看日志了解详细信息！",
                QMessageBox.Ok
            )
            import traceback
            traceback.print_exc()
        finally:
            # 恢复按钮状态
            self.run_btn.setEnabled(True)
            self.run_btn.setText("执行更新")


if __name__ == "__main__":
    # 创建应用程序实例
    app = QApplication(sys.argv)
    # 全局设置中文字体，解决乱码问题
    app.setFont(QFont("Microsoft YaHei"))
    # 创建主窗口并显示
    window = ExcelUpdateGUI()
    window.show()
    # 运行应用程序主循环
    sys.exit(app.exec())