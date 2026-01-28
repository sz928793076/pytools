import sys
import json
import re
import pandas as pd
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QTableView, QHeaderView, QLabel,
    QMessageBox, QFileDialog, QDialog, QComboBox, QLineEdit,
    QListWidget, QAbstractItemView, QGroupBox, QInputDialog, QFormLayout
)
from PyQt6.QtCore import Qt, QAbstractTableModel

# 必須在任何 PyQt6 匯入之後才能匯入 qt-material
from qt_material import apply_stylesheet


# --------------------------
# 工具函數：驼峰转下划线
# --------------------------
def camel_to_snake(name):
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


# --------------------------
# Pandas 数据模型
# --------------------------
class PandasModel(QAbstractTableModel):
    def __init__(self, df=pd.DataFrame(), parent=None):
        super().__init__(parent)
        self._df = df

    def rowCount(self, parent=None):
        return self._df.shape[0]

    def columnCount(self, parent=None):
        return self._df.shape[1]

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if index.isValid() and role == Qt.ItemDataRole.DisplayRole:
            val = self._df.iloc[index.row(), index.column()]
            return str(val)
        return None

    def headerData(self, col, orientation, role):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self._df.columns[col]
        return None

    def sort(self, column, order):
        col_name = self._df.columns[column]
        self.layoutAboutToBeChanged.emit()
        ascending = (order == Qt.SortOrder.AscendingOrder)
        self._df.sort_values(col_name, ascending=ascending, inplace=True)
        self.layoutChanged.emit()

    def get_dataframe(self):
        return self._df


# --------------------------
# 筛选对话框
# --------------------------
class FilterDialog(QDialog):
    def __init__(self, df, parent=None):
        super().__init__(parent)
        self.df = df
        self.result_filter = None
        self.setWindowTitle("添加筛选条件")
        self.resize(520, 420)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        form_layout = QFormLayout()
        form_layout.setSpacing(10)
        self.combo_field = QComboBox()
        self.combo_field.addItems(self.df.columns.tolist())
        self.combo_field.currentTextChanged.connect(self.on_field_changed)
        form_layout.addRow("选择字段:", self.combo_field)
        layout.addLayout(form_layout)

        layout.addWidget(QLabel("该字段现有值（可多选用 于 IN）："))

        self.list_values = QListWidget()
        self.list_values.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list_values.itemClicked.connect(self.on_value_clicked)
        layout.addWidget(self.list_values)

        control_layout = QHBoxLayout()
        control_layout.setSpacing(10)

        self.combo_op = QComboBox()
        self.combo_op.addItems([
            "包含（模糊）", "等于 (=)", "不等于 (!=)",
            "大于 (>)", "小于 (<)", "在集合中 (IN)"
        ])

        self.input_val = QLineEdit()
        self.input_val.setPlaceholderText("输入值 或 从上方列表选择")

        control_layout.addWidget(self.combo_op, 1)
        control_layout.addWidget(self.input_val, 3)
        layout.addLayout(control_layout)

        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("确定添加")
        btn_cancel = QPushButton("取消")
        btn_ok.clicked.connect(self.apply_filter)
        btn_cancel.clicked.connect(self.reject)

        btn_layout.addStretch()
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

        self.on_field_changed(self.combo_field.currentText())

    def on_field_changed(self, text):
        self.list_values.clear()
        if text in self.df.columns:
            unique_vals = self.df[text].dropna().unique()
            try:
                sorted_vals = sorted(unique_vals, key=lambda x: str(x))
            except:
                sorted_vals = unique_vals
            for val in sorted_vals:
                self.list_values.addItem(str(val))

    def on_value_clicked(self, item):
        op = self.combo_op.currentText()
        if "IN" in op:
            current = self.input_val.text().strip()
            selected = [i.text() for i in self.list_values.selectedItems()]
            if current:
                self.input_val.setText(current + "," + ",".join(selected))
            else:
                self.input_val.setText(",".join(selected))
        else:
            self.input_val.setText(item.text())

    def apply_filter(self):
        field = self.combo_field.currentText()
        op = self.combo_op.currentText()
        val = self.input_val.text().strip()

        if not val:
            QMessageBox.warning(self, "警告", "请输入筛选值")
            return

        self.result_filter = {"field": field, "op": op, "val": val}
        self.accept()


# --------------------------
# 主窗口
# --------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("JSON 转表格 & SQL/CSV 导出工具")
        self.resize(1100, 780)

        self.original_df = pd.DataFrame()
        self.current_df = pd.DataFrame()
        self.filters = []

        self.setup_ui()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(14)
        main_layout.setContentsMargins(16, 16, 16, 16)

        # 1. JSON 输入区
        input_group = QGroupBox("1. 粘贴 JSON 数据")
        input_layout = QVBoxLayout()

        self.text_input = QTextEdit()
        self.text_input.setPlaceholderText("在此粘贴 JSON 数组，例如：[{...}, {...}]")
        self.text_input.setMinimumHeight(100)

        self.btn_parse = QPushButton("解析 JSON 并显示")
        self.btn_parse.clicked.connect(self.parse_json)

        input_layout.addWidget(self.text_input)
        input_layout.addWidget(self.btn_parse, alignment=Qt.AlignmentFlag.AlignRight)
        input_group.setLayout(input_layout)
        main_layout.addWidget(input_group)

        # 2. 筛选区
        filter_group = QGroupBox("2. 数据筛选（基于当前结果）")
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(12)

        self.btn_add_filter = QPushButton("添加筛选条件")
        self.btn_add_filter.clicked.connect(self.open_filter_dialog)

        self.btn_reset_filter = QPushButton("重置所有筛选")
        self.btn_reset_filter.clicked.connect(self.reset_filters)

        self.lbl_status = QLabel("当前无筛选条件")
        self.lbl_status.setStyleSheet("color: #666666; font-style: italic;")

        filter_layout.addWidget(self.btn_add_filter)
        filter_layout.addWidget(self.btn_reset_filter)
        filter_layout.addWidget(self.lbl_status)
        filter_layout.addStretch()
        filter_group.setLayout(filter_layout)
        main_layout.addWidget(filter_group)

        # 3. 表格显示区（重点：动态宽度）
        self.table_view = QTableView()
        self.table_view.setSortingEnabled(True)

        # 表头设置 - 允许用户手动拖拽调整 + 最后一栏自动拉伸
        header = self.table_view.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)  # 用户可拖拽
        header.setStretchLastSection(True)  # 最后一栏自动填充剩余空间

        main_layout.addWidget(self.table_view, stretch=1)

        # 4. 导出区
        export_group = QGroupBox("3. 导出当前表格内容")
        export_layout = QHBoxLayout()
        export_layout.setSpacing(12)

        self.btn_csv = QPushButton("导出 CSV")
        self.btn_csv.clicked.connect(self.export_csv)

        self.btn_sql = QPushButton("导出 SQL")
        self.btn_sql.clicked.connect(self.export_sql)

        export_layout.addStretch()
        export_layout.addWidget(self.btn_csv)
        export_layout.addWidget(self.btn_sql)
        export_group.setLayout(export_layout)
        main_layout.addWidget(export_group)

    def parse_json(self):
        json_str = self.text_input.toPlainText().strip()
        if not json_str:
            return

        try:
            data = json.loads(json_str)
            if isinstance(data, dict):
                data = [data]

            if not isinstance(data, list):
                raise ValueError("JSON 必须是对象数组或单个对象")

            self.original_df = pd.DataFrame(data)
            self.current_df = self.original_df.copy()

            # 更新表格并自动调整列宽
            self.update_table(self.current_df)

            # 重要：資料載入後立即調整欄寬（根據內容）
            self.table_view.resizeColumnsToContents()

            self.text_input.clear()
            self.filters = []
            self.update_filter_status()

            QMessageBox.information(self, "成功", f"解析完成，共 {len(self.current_df)} 条数据。\n输入框已清空。")
        except Exception as e:
            QMessageBox.critical(self, "解析失败", str(e))

    def update_table(self, df):
        model = PandasModel(df)
        self.table_view.setModel(model)
        # 可選：每次更新資料後也調整一次欄寬（篩選後也適用）
        # self.table_view.resizeColumnsToContents()

    def open_filter_dialog(self):
        if self.original_df.empty:
            QMessageBox.warning(self, "提示", "请先解析 JSON 数据")
            return

        dialog = FilterDialog(self.current_df, self)
        if dialog.exec():
            f = dialog.result_filter
            self.filters.append(f)
            self.apply_filters_logic()

    def reset_filters(self):
        self.filters = []
        self.apply_filters_logic()

    def apply_filters_logic(self):
        temp_df = self.original_df.copy()
        descriptions = []

        try:
            for f in self.filters:
                field = f['field']
                op = f['op']
                val = f['val']

                desc = f"{field} {op} {val}"
                descriptions.append(desc)

                is_numeric = pd.api.types.is_numeric_dtype(temp_df[field])

                if "包含" in op:
                    temp_df = temp_df[temp_df[field].astype(str).str.contains(val, case=False, na=False)]
                elif "IN" in op:
                    val_list = [v.strip() for v in val.split(",")]
                    if is_numeric:
                        try:
                            val_list = [float(v) if '.' in v else int(v) for v in val_list]
                        except:
                            pass
                    temp_df = temp_df[temp_df[field].isin(val_list)]
                else:
                    comp_val = val
                    if is_numeric:
                        try:
                            comp_val = float(val)
                        except:
                            pass

                    if "等于" in op:
                        temp_df = temp_df[temp_df[field] == comp_val]
                    elif "不等于" in op:
                        temp_df = temp_df[temp_df[field] != comp_val]
                    elif "大于" in op:
                        temp_df = temp_df[temp_df[field] > comp_val]
                    elif "小于" in op:
                        temp_df = temp_df[temp_df[field] < comp_val]

            self.current_df = temp_df
            self.update_table(self.current_df)

            # 篩選後也重新調整欄寬
            self.table_view.resizeColumnsToContents()

            self.update_filter_status(descriptions)

        except Exception as e:
            QMessageBox.critical(self, "筛选错误", f"应用筛选条件时发生错误:\n{str(e)}")
            if self.filters:
                self.filters.pop()

    def update_filter_status(self, descs=None):
        if not descs:
            self.lbl_status.setText("当前无筛选条件（显示全部数据）")
        else:
            text = " && ".join(descs)
            self.lbl_status.setText(f"当前筛选：{text}")

    def export_csv(self):
        if self.current_df.empty:
            QMessageBox.warning(self, "提示", "没有数据可导出")
            return

        path, _ = QFileDialog.getSaveFileName(self, "保存 CSV", "", "CSV 文件 (*.csv)")
        if path:
            try:
                df = self.table_view.model().get_dataframe()
                df.to_csv(path, index=False, encoding='utf-8-sig')
                QMessageBox.information(self, "成功", "CSV 导出完成！")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导出失败：{str(e)}")

    def export_sql(self):
        if self.current_df.empty:
            QMessageBox.warning(self, "提示", "没有数据可导出")
            return

        table_name, ok = QInputDialog.getText(self, "导出 SQL", "请输入表名：", text="my_table")
        if not ok or not table_name.strip():
            return

        path, _ = QFileDialog.getSaveFileName(self, "保存 SQL", "", "SQL 文件 (*.sql)")
        if not path:
            return

        try:
            model = self.table_view.model()
            df = model.get_dataframe().copy()

            new_cols = [camel_to_snake(c) for c in df.columns]
            df.columns = new_cols

            cols_str = ", ".join([f"`{c}`" for c in new_cols])
            sql_statements = []

            for _, row in df.iterrows():
                vals = []
                for val in row:
                    if pd.isna(val):
                        vals.append("NULL")
                    elif isinstance(val, (int, float)):
                        vals.append(str(val))
                    else:
                        clean = str(val).replace("'", "''")
                        vals.append(f"'{clean}'")
                vals_str = ", ".join(vals)
                sql = f"INSERT INTO `{table_name}` ({cols_str}) VALUES ({vals_str});"
                sql_statements.append(sql)

            with open(path, 'w', encoding='utf-8') as f:
                f.write(f"-- 从 JSON 数据导出 - 表名：{table_name}\n\n")
                f.write("\n".join(sql_statements))

            QMessageBox.information(self, "成功", "SQL 导出完成！")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"SQL 导出失败：{str(e)}")


if __name__ == '__main__':
    app = QApplication(sys.argv)

    # 使用亮色主題 - light_teal.xml（清新青藍色調）
    # 加上 invert_secondary=True 改善亮色模式下的對比度
    apply_stylesheet(app, theme='light_teal.xml', invert_secondary=True)

    # 其他亮色主題備選（可自行替換）：
    # apply_stylesheet(app, theme='light_blue.xml', invert_secondary=True)
    # apply_stylesheet(app, theme='light_green.xml', invert_secondary=True)
    # apply_stylesheet(app, theme='light_purple.xml', invert_secondary=True)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())