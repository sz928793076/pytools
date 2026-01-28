import sys
import json
import re
import pandas as pd
from PyQt6.QtGui import QFont, QAction
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTextEdit,
    QPushButton,
    QLabel,
    QTableView,
    QComboBox,
    QMessageBox,
    QFileDialog,
    QInputDialog,
    QHeaderView,
    QAbstractItemView,
    QListWidget,
    QGroupBox,
    QFrame,
    QDialog,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QMenuBar
)

from PyQt6.QtCore import (
    Qt,
    QAbstractTableModel,
    QSettings
)

# 尝试导入 SQLAlchemy，如果没有安装则会在运行时提示
try:
    from sqlalchemy import create_engine

    HAS_SQLALCHEMY = True
except ImportError:
    HAS_SQLALCHEMY = False


# ==================== 工具函数 ====================
def camel_to_snake(name):
    """将驼峰命名转换为下划线命名"""
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


# ==================== 数据库配置弹窗类 ====================
class DbConfigDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("数据库连接配置")
        self.setFixedSize(400, 300)

        # 使用 QSettings 进行持久化存储
        # 组织名: MyTools, 应用名: JsonConverter
        self.settings = QSettings("MyTools", "JsonConverter")

        self.init_ui()
        self.load_settings()

    def init_ui(self):
        layout = QVBoxLayout()
        form_layout = QFormLayout()
        form_layout.setSpacing(15)

        # 控件定义
        self.input_host = QLineEdit()
        self.input_host.setPlaceholderText("例如: 127.0.0.1")

        self.input_port = QSpinBox()
        self.input_port.setRange(1, 65535)
        self.input_port.setValue(3306)

        self.input_user = QLineEdit()
        self.input_user.setPlaceholderText("例如: root")

        self.input_password = QLineEdit()
        self.input_password.setEchoMode(QLineEdit.EchoMode.Password)

        self.input_db = QLineEdit()
        self.input_db.setPlaceholderText("目标数据库名称")

        self.combo_type = QComboBox()
        self.combo_type.addItems(["mysql+pymysql", "postgresql", "sqlite", "mssql+pymssql"])

        # 添加到布局
        form_layout.addRow("数据库类型:", self.combo_type)
        form_layout.addRow("主机 (Host):", self.input_host)
        form_layout.addRow("端口 (Port):", self.input_port)
        form_layout.addRow("用户名 (User):", self.input_user)
        form_layout.addRow("密码 (Pass):", self.input_password)
        form_layout.addRow("库名 (DB Name):", self.input_db)

        layout.addLayout(form_layout)

        # 按钮区
        btn_layout = QHBoxLayout()
        btn_save = QPushButton("保存配置")
        btn_save.clicked.connect(self.save_settings)
        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(self.reject)

        btn_layout.addStretch()
        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_cancel)

        layout.addStretch()
        layout.addLayout(btn_layout)
        self.setLayout(layout)

    def load_settings(self):
        """加载保存的配置"""
        self.input_host.setText(self.settings.value("db_host", "127.0.0.1"))
        self.input_port.setValue(int(self.settings.value("db_port", 3306)))
        self.input_user.setText(self.settings.value("db_user", "root"))
        self.input_password.setText(self.settings.value("db_pass", ""))
        self.input_db.setText(self.settings.value("db_name", ""))

        current_type = self.settings.value("db_type", "mysql+pymysql")
        idx = self.combo_type.findText(current_type)
        if idx >= 0:
            self.combo_type.setCurrentIndex(idx)

    def save_settings(self):
        """保存配置到系统"""
        self.settings.setValue("db_host", self.input_host.text().strip())
        self.settings.setValue("db_port", self.input_port.value())
        self.settings.setValue("db_user", self.input_user.text().strip())
        self.settings.setValue("db_pass", self.input_password.text())
        self.settings.setValue("db_name", self.input_db.text().strip())
        self.settings.setValue("db_type", self.combo_type.currentText())

        QMessageBox.information(self, "成功", "配置已保存！")
        self.accept()

    def get_connection_info(self):
        """返回配置字典"""
        return {
            "type": self.combo_type.currentText(),
            "host": self.input_host.text().strip(),
            "port": self.input_port.value(),
            "user": self.input_user.text().strip(),
            "password": self.input_password.text(),
            "db": self.input_db.text().strip()
        }


# ==================== Pandas 模型类 ====================
class PandasModel(QAbstractTableModel):
    def __init__(self, data):
        super().__init__()
        self._data = data

    def rowCount(self, parent=None):
        return self._data.shape[0]

    def columnCount(self, parent=None):
        return self._data.shape[1]

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if index.isValid() and role == Qt.ItemDataRole.DisplayRole:
            return str(self._data.iloc[index.row(), index.column()])
        return None

    def headerData(self, col, orientation, role):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self._data.columns[col]
        return None

    def sort(self, column, order):
        col_name = self._data.columns[column]
        is_asc = (order == Qt.SortOrder.AscendingOrder)
        self._data = self._data.sort_values(by=col_name, ascending=is_asc, na_position='last')
        self.layoutChanged.emit()


# ==================== 主窗口类 ====================
class JsonConverterApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("JSON 数据表格工具")
        self.resize(1280, 860)

        self.df_original = pd.DataFrame()
        self.df_current = pd.DataFrame()
        self.active_filters = []

        self.init_menu()  # 初始化菜单
        self.init_ui()
        self.apply_styles()

    def init_menu(self):
        """初始化顶部菜单栏"""
        menubar = self.menuBar()
        setting_menu = menubar.addMenu("设置(S)")

        db_config_action = QAction("数据库配置...", self)
        db_config_action.setShortcut("Ctrl+D")
        db_config_action.triggered.connect(self.open_db_config)
        setting_menu.addAction(db_config_action)

    def apply_styles(self):
        """统一美化样式"""
        self.setStyleSheet("""
            QPushButton {
                background-color: #1976d2;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 500;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #1565c0; }
            QPushButton:pressed { background-color: #0d47a1; }
            QPushButton:disabled { background-color: #90caf9; color: #e3f2fd; }

            /* 导出类按钮（玫红色） */
            QPushButton#exportBtn {
                background-color: #d81b60;
                font-weight: bold;
            }
            QPushButton#exportBtn:hover { background-color: #c2185b; }
            QPushButton#exportBtn:pressed { background-color: #ad1457; }

            /* 数据库插入按钮（紫色） */
            QPushButton#dbInsertBtn {
                background-color: #7b1fa2;
                font-weight: bold;
            }
            QPushButton#dbInsertBtn:hover { background-color: #6a1b9a; }
            QPushButton#dbInsertBtn:pressed { background-color: #4a148c; }

            QListWidget {
                background: white;
                border: 1px solid #ccd6e2;
                border-radius: 6px;
                padding: 4px;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #ccd6e2;
                border-radius: 6px;
                margin-top: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 10px;
                color: #1976d2;
            }
            QTableView {
                alternate-background-color: #f5faff;
                gridline-color: #e0e0e0;
            }
        """)
        font = QFont("Microsoft YaHei", 10)
        QApplication.setFont(font)

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(16, 16, 16, 16)

        # ==================== 顶部控制区 ====================
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        top_layout.setSpacing(14)

        # 1. JSON 输入
        json_group = QGroupBox("1. 粘贴 JSON 数据")
        json_layout = QHBoxLayout()
        json_layout.setContentsMargins(12, 18, 12, 12)
        self.json_input = QTextEdit()
        self.json_input.setPlaceholderText('示例：[{"id":1,"name":"张三","age":25}, ...]')
        self.json_input.setMaximumHeight(80)
        json_layout.addWidget(self.json_input, stretch=5)
        btn_parse = QPushButton("解析 JSON")
        btn_parse.setFixedSize(110, 70)
        btn_parse.clicked.connect(self.load_json_data)
        json_layout.addWidget(btn_parse)
        json_group.setLayout(json_layout)
        top_layout.addWidget(json_group)

        # 2. 筛选条件
        filter_group = QGroupBox("2. 添加筛选条件")
        filter_layout = QHBoxLayout()
        filter_layout.setContentsMargins(12, 18, 12, 12)
        filter_layout.setSpacing(10)
        filter_layout.addWidget(QLabel("字段："))
        self.combo_columns = QComboBox()
        self.combo_columns.setMinimumWidth(160)
        self.combo_columns.currentIndexChanged.connect(self.update_value_options)
        filter_layout.addWidget(self.combo_columns)
        filter_layout.addWidget(QLabel("操作："))
        self.combo_ops = QComboBox()
        self.combo_ops.addItems(["包含", "等于", "大于", "小于", "在集合中"])
        self.combo_ops.setFixedWidth(130)
        filter_layout.addWidget(self.combo_ops)
        filter_layout.addWidget(QLabel("值："))
        self.combo_values = QComboBox()
        self.combo_values.setEditable(True)
        self.combo_values.setMinimumWidth(180)
        filter_layout.addWidget(self.combo_values)
        btn_add = QPushButton("➕ 添加条件")
        btn_add.setFixedWidth(110)
        btn_add.clicked.connect(self.add_filter_condition)
        filter_layout.addWidget(btn_add)
        filter_group.setLayout(filter_layout)
        top_layout.addWidget(filter_group)

        # 3. 列表与导出
        filter_status_layout = QHBoxLayout()
        filter_status_layout.setSpacing(16)

        filter_list_frame = QFrame()
        filter_list_layout = QVBoxLayout(filter_list_frame)
        filter_list_layout.addWidget(QLabel("当前筛选条件（双击删除）："))
        self.list_filters = QListWidget()
        self.list_filters.setMaximumHeight(130)  # 稍微调高一点适应新按钮
        self.list_filters.itemDoubleClicked.connect(self.remove_filter_condition)
        filter_list_layout.addWidget(self.list_filters)
        filter_status_layout.addWidget(filter_list_frame, stretch=5)

        # === 导出按钮区域 (修改了这里) ===
        export_btn_layout = QVBoxLayout()
        export_btn_layout.setSpacing(8)

        btn_csv = QPushButton("导出为 CSV")
        btn_csv.setObjectName("exportBtn")
        btn_csv.setFixedHeight(38)
        btn_csv.clicked.connect(self.export_csv)
        export_btn_layout.addWidget(btn_csv)

        btn_sql = QPushButton("导出为 SQL")
        btn_sql.setObjectName("exportBtn")
        btn_sql.setFixedHeight(38)
        btn_sql.clicked.connect(self.export_sql)
        export_btn_layout.addWidget(btn_sql)

        # 新增按钮：插入数据库
        btn_db_insert = QPushButton("插入数据库")
        btn_db_insert.setObjectName("dbInsertBtn")  # 使用紫色样式
        btn_db_insert.setFixedHeight(38)
        btn_db_insert.clicked.connect(self.insert_to_database)
        export_btn_layout.addWidget(btn_db_insert)

        export_btn_layout.addStretch()
        filter_status_layout.addLayout(export_btn_layout, stretch=1)
        top_layout.addLayout(filter_status_layout)
        main_layout.addWidget(top_widget)

        # ==================== 表格区域 ====================
        table_group = QGroupBox("3. 数据表格")
        table_layout = QVBoxLayout()
        self.table_view = QTableView()
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setSortingEnabled(True)
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table_view.horizontalHeader().setStretchLastSection(True)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_view.verticalHeader().setVisible(False)
        table_layout.addWidget(self.table_view)
        table_group.setLayout(table_layout)
        main_layout.addWidget(table_group, stretch=1)

    # ==================== 逻辑方法 ====================

    def open_db_config(self):
        """打开数据库配置弹窗"""
        dialog = DbConfigDialog(self)
        dialog.exec()

    def insert_to_database(self):
        """将当前表格数据直接插入数据库"""
        if not HAS_SQLALCHEMY:
            QMessageBox.critical(self, "缺少依赖",
                                 "请先安装 sqlalchemy 和 数据库驱动。\n例如：pip install sqlalchemy pymysql")
            return

        if self.df_current.empty:
            QMessageBox.warning(self, "提示", "当前没有数据可插入")
            return

        # 1. 检查配置是否存在
        settings = QSettings("MyTools", "JsonConverter")
        db_host = settings.value("db_host")
        db_user = settings.value("db_user")
        db_name = settings.value("db_name")

        if not db_host or not db_user:
            ret = QMessageBox.question(self, "未配置", "数据库尚未配置，是否立即配置？",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if ret == QMessageBox.StandardButton.Yes:
                self.open_db_config()
                # 重新检查
                if not settings.value("db_host"):
                    return
            else:
                return

        # 2. 获取表名
        table_name, ok = QInputDialog.getText(self, "插入数据库", "请输入目标表名：", text="my_table")
        if not ok or not table_name.strip():
            return
        table_name = table_name.strip()

        # 3. 确认插入方式
        items = ["追加 (Append)", "替换 (Replace - 慎用)", "失败则报错 (Fail)"]
        item, ok = QInputDialog.getItem(self, "插入模式", "请选择插入模式：", items, 0, False)
        if not ok:
            return

        if "Append" in item:
            if_exists_mode = 'append'
        elif "Replace" in item:
            if_exists_mode = 'replace'
        else:
            if_exists_mode = 'fail'

        # 4. 执行插入
        try:
            # 读取配置构建 Connection String
            db_type = settings.value("db_type", "mysql+pymysql")
            db_port = settings.value("db_port", 3306)
            db_pass = settings.value("db_pass", "")

            # 构建 SQLAlchemy URL
            # 格式: mysql+pymysql://user:password@host:port/dbname
            # 注意：如果密码包含特殊字符，建议使用 urllib.parse.quote_plus 处理，这里简化处理
            conn_str = f"{db_type}://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"

            # 创建引擎
            engine = create_engine(conn_str)

            # 获取当前数据
            df = self.get_current_table_data()

            # 自动处理列名（驼峰转下划线），保持数据库规范
            df_to_save = df.copy()
            df_to_save.columns = [camel_to_snake(c) for c in df_to_save.columns]

            # 写入数据库
            df_to_save.to_sql(name=table_name, con=engine, if_exists=if_exists_mode, index=False)

            QMessageBox.information(self, "成功", f"成功插入 {len(df_to_save)} 条数据到表 `{table_name}`")

        except Exception as e:
            QMessageBox.critical(self, "插入失败", f"数据库错误：\n{str(e)}\n\n请检查配置或表结构。")

    def load_json_data(self):
        text = self.json_input.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "提示", "请输入 JSON 数据")
            return
        try:
            data = json.loads(text)
            if isinstance(data, dict): data = [data]
            if not isinstance(data, list):
                QMessageBox.critical(self, "错误", "JSON 格式必须是列表或单个对象")
                return
            self.df_original = pd.DataFrame(data)
            for col in self.df_original.columns:
                self.df_original[col] = pd.to_numeric(self.df_original[col], errors='ignore')
            self.active_filters = []
            self.list_filters.clear()
            self.refresh_filter_columns()
            self.apply_all_filters()
            QMessageBox.information(self, "加载成功", f"共加载 {len(self.df_original)} 条记录")
        except Exception as e:
            QMessageBox.critical(self, "加载失败", str(e))

    def refresh_filter_columns(self):
        self.combo_columns.clear()
        if not self.df_original.empty:
            cols = self.df_original.columns.tolist()
            self.combo_columns.addItems(cols)
            self.update_value_options()

    def update_value_options(self):
        col = self.combo_columns.currentText()
        self.combo_values.clear()
        if col and col in self.df_original.columns:
            vals = self.df_original[col].dropna().unique()
            sorted_vals = sorted(vals, key=lambda x: str(x))
            self.combo_values.addItems([str(v) for v in sorted_vals[:300]])

    def add_filter_condition(self):
        if self.df_original.empty:
            QMessageBox.warning(self, "提示", "请先加载数据")
            return
        col = self.combo_columns.currentText()
        op = self.combo_ops.currentText()
        val = self.combo_values.currentText().strip()
        if not col or not val:
            QMessageBox.warning(self, "提示", "字段和值不能为空")
            return
        self.active_filters.append((col, op, val))
        self.list_filters.addItem(f"【{col}】 {op} '{val}'")
        self.apply_all_filters()

    def remove_filter_condition(self, item):
        row = self.list_filters.row(item)
        if row >= 0:
            self.list_filters.takeItem(row)
            self.active_filters.pop(row)
            self.apply_all_filters()

    def apply_all_filters(self):
        if self.df_original.empty: return
        df = self.df_original.copy()
        try:
            for col, op, val_text in self.active_filters:
                is_num = pd.api.types.is_numeric_dtype(df[col])
                if op == "包含":
                    df = df[df[col].astype(str).str.contains(val_text, case=False, na=False)]
                elif op == "在集合中":
                    parts = [v.strip() for v in val_text.split(',')]
                    if is_num:
                        nums = []
                        for p in parts:
                            try:
                                nums.append(float(p) if '.' in p else int(p))
                            except:
                                pass
                        df = df[df[col].isin(nums) if nums else df[col].astype(str).isin(parts)]
                    else:
                        df = df[col].astype(str).isin(parts)
                else:
                    t_val = val_text
                    if is_num:
                        try:
                            t_val = float(val_text)
                        except:
                            pass
                    if op == "等于":
                        df = df[df[col] == t_val]
                    elif op == "大于":
                        df = df[df[col] > t_val]
                    elif op == "小于":
                        df = df[df[col] < t_val]
            self.df_current = df
            self.refresh_table()
        except Exception as e:
            QMessageBox.warning(self, "筛选错误", str(e))

    def refresh_table(self):
        model = PandasModel(self.df_current)
        self.table_view.setModel(model)
        self.table_view.resizeColumnsToContents()
        h = self.table_view.horizontalHeader()
        for i in range(h.count()):
            w = h.sectionSize(i)
            if w < 90: h.resizeSection(i, 90)
            if w > 420: h.resizeSection(i, 420)

    def get_current_table_data(self):
        model = self.table_view.model()
        if model and hasattr(model, '_data'): return model._data.copy()
        return self.df_current.copy()

    def export_csv(self):
        if self.df_current.empty:
            QMessageBox.warning(self, "提示", "没有数据可导出")
            return
        file_path, _ = QFileDialog.getSaveFileName(self, "保存为 CSV", "", "CSV 文件 (*.csv);;所有文件 (*.*)")
        if not file_path: return
        try:
            df = self.get_current_table_data()
            df.to_csv(file_path, index=False, encoding='utf-8-sig')
            QMessageBox.information(self, "成功", f"已保存至：\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "失败", str(e))

    def export_sql(self):
        if self.df_current.empty:
            QMessageBox.warning(self, "提示", "没有数据可导出")
            return
        table_name, ok = QInputDialog.getText(self, "导出 SQL", "请输入表名：", text="my_table")
        if not ok or not table_name.strip(): return
        batch_size, ok = QInputDialog.getInt(self, "批量设置", "每批次记录数：", value=1000, min=1)
        if not ok: return
        file_path, _ = QFileDialog.getSaveFileName(self, "保存为 SQL", "", "SQL 文件 (*.sql)")
        if not file_path: return
        try:
            df = self.get_current_table_data()
            cols = [camel_to_snake(c) for c in df.columns]
            col_str = ", ".join(f"`{c}`" for c in cols)
            sql_lines = [f"-- 批量插入 `{table_name}`"]
            total_rows = len(df)
            for start in range(0, total_rows, batch_size):
                end = min(start + batch_size, total_rows)
                batch_df = df.iloc[start:end]
                batch_vals = []
                for _, row in batch_df.iterrows():
                    vals = []
                    for val in row:
                        if pd.isna(val):
                            vals.append("NULL")
                        elif isinstance(val, (int, float)):
                            vals.append(str(val))
                        else:
                            vals.append(f"'{str(val).replace("'", "''")}'")
                    batch_vals.append(f"({', '.join(vals)})")
                if batch_vals:
                    sql_lines.append(
                        f"INSERT INTO `{table_name}` ({col_str}) VALUES\n    {',\n    '.join(batch_vals)};")
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write("\n\n".join(sql_lines))
            QMessageBox.information(self, "成功", f"已导出到 {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "失败", str(e))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = JsonConverterApp()
    window.show()
    sys.exit(app.exec())