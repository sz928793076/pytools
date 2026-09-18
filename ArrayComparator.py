import sys
import json
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QTextEdit, QPushButton, QGroupBox
)
from PySide6.QtCore import Qt


class ArrayComparator(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("JSON 数组差值比较工具")
        self.setMinimumSize(800, 600)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # 输入区域：两个 JSON 数组
        # 数组 A
        group_a = QGroupBox("数组 A（第一个数组）")
        group_a_layout = QVBoxLayout()
        self.text_a = QTextEdit()
        self.text_a.setPlaceholderText('例如：["a", "b", "c"]  或  [{"id":1}, {"id":2}]')
        group_a_layout.addWidget(self.text_a)
        group_a.setLayout(group_a_layout)
        layout.addWidget(group_a)

        # 数组 B
        group_b = QGroupBox("数组 B（第二个数组）")
        group_b_layout = QVBoxLayout()
        self.text_b = QTextEdit()
        self.text_b.setPlaceholderText('例如：["a", "b"]')
        group_b_layout.addWidget(self.text_b)
        group_b.setLayout(group_b_layout)
        layout.addWidget(group_b)

        # 说明标签（解释计算逻辑）
        info_label = QLabel("说明：点击按钮后，将输出「数组 A 中有而数组 B 中没有的元素」（即 A - B 的差集）")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # 按钮
        self.btn_compare = QPushButton("计算多出的元素")
        self.btn_compare.clicked.connect(self.compare_arrays)
        layout.addWidget(self.btn_compare)

        # 输出区域
        output_group = QGroupBox("多出的元素（数组 A 比数组 B 多出的部分）")
        output_layout = QVBoxLayout()
        self.text_output = QTextEdit()
        self.text_output.setReadOnly(True)
        self.text_output.setPlaceholderText("结果将以 JSON 数组形式显示...")
        output_layout.addWidget(self.text_output)
        output_group.setLayout(output_layout)
        layout.addWidget(output_group)

    def compare_arrays(self):
        """读取两个数组，计算 A - B，并输出"""
        # 清空输出
        self.text_output.clear()

        # 获取文本
        text_a = self.text_a.toPlainText().strip()
        text_b = self.text_b.toPlainText().strip()

        if not text_a:
            self.text_output.setText("错误：数组 A 不能为空")
            return

        # 解析 JSON
        try:
            list_a = json.loads(text_a)
        except json.JSONDecodeError as e:
            self.text_output.setText(f"数组 A JSON 解析失败：{str(e)}")
            return

        try:
            list_b = json.loads(text_b) if text_b else []
        except json.JSONDecodeError as e:
            self.text_output.setText(f"数组 B JSON 解析失败：{str(e)}")
            return

        # 确保是列表
        if not isinstance(list_a, list):
            self.text_output.setText("数组 A 必须是一个 JSON 数组（以 [ 开头 ] 结尾）")
            return
        if not isinstance(list_b, list):
            self.text_output.setText("数组 B 必须是一个 JSON 数组（以 [ 开头 ] 结尾）")
            return

        # 计算差集：A 中有但 B 中没有的元素
        # 由于元素可能是字典等不可哈希对象，使用 JSON 序列化后的字符串进行比较
        def normalize(item):
            """将元素转为可比较的字符串（JSON 格式）"""
            # 对于字符串、数字等基本类型，直接转 JSON 字符串
            # 使用 sort_keys 确保字典顺序一致
            return json.dumps(item, sort_keys=True, ensure_ascii=False)

        set_b = {normalize(item) for item in list_b}
        diff = [item for item in list_a if normalize(item) not in set_b]

        # 格式化输出
        output_text = json.dumps(diff, indent=2, ensure_ascii=False)
        self.text_output.setText(output_text)

        # 显示统计信息
        status = f"数组 A 共 {len(list_a)} 条，数组 B 共 {len(list_b)} 条，多出 {len(diff)} 条。"
        self.statusBar().showMessage(status)


def main():
    app = QApplication(sys.argv)
    window = ArrayComparator()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()