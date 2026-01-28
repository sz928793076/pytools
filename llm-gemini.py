import sys
import json
import os
from PIL import Image
from google import genai
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QLineEdit, QPushButton, QLabel, QScrollArea,
    QComboBox, QFileDialog, QFrame
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QPixmap, QFont

CONFIG_FILE = "config.json"

# --- 🎨 样式表 (已修复下拉框配色) ---
STYLESHEET = """
/* 全局设定 */
QMainWindow { background-color: #1e1e2e; }
QWidget { font-family: "Segoe UI", "Microsoft YaHei", sans-serif; font-size: 14px; color: #cdd6f4; }

/* 顶部栏 */
QFrame#TopBar { background-color: #181825; border-bottom: 1px solid #313244; }

/* 输入框通用 */
QLineEdit { 
    background-color: #313244; 
    border: 1px solid #45475a; 
    border-radius: 8px; 
    padding: 5px 10px; 
    color: #cdd6f4; 
}
QLineEdit:focus { border: 1px solid #89b4fa; }

/* --- 🔧 下拉框核心修复 --- */
QComboBox {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 8px;
    padding: 5px 10px;
    color: #cdd6f4;
}
QComboBox:on { /* 点击时 */
    border: 1px solid #89b4fa;
}
QComboBox::drop-down {
    border: 0px; /* 去掉下拉箭头边框 */
    width: 20px;
}
/* ⬇️ 下拉列表弹出的部分 ⬇️ */
QComboBox QAbstractItemView {
    background-color: #181825; /* 列表背景改深色 */
    color: #cdd6f4;            /* 文字改浅色 */
    selection-background-color: #45475a; /* 鼠标悬停背景 */
    selection-color: #ffffff;  /* 鼠标悬停文字 */
    border: 1px solid #45475a;
    outline: none;
}

/* 聊天显示区 */
QScrollArea { border: none; background-color: #1e1e2e; }
QWidget#ChatContent { background-color: #1e1e2e; }

/* 底部输入区 */
QFrame#InputArea { background-color: #181825; border-top: 1px solid #313244; }
QTextEdit { 
    background-color: #313244; 
    border: 1px solid #45475a; 
    border-radius: 12px; 
    padding: 10px; 
    color: #cdd6f4; 
}

/* 按钮样式 */
QPushButton { 
    background-color: #313244; 
    border-radius: 8px; 
    padding: 6px 15px; 
    font-weight: bold; 
    border: 1px solid #45475a;
}
QPushButton:hover { background-color: #45475a; border-color: #585b70; }
QPushButton#SendBtn { background-color: #89b4fa; color: #1e1e2e; border: none; }
QPushButton#SendBtn:hover { background-color: #b4befe; }
QPushButton#RefreshBtn { width: 30px; }

/* 气泡样式 */
QFrame#BubbleAI { background-color: #313244; border-radius: 15px; border-bottom-left-radius: 2px; }
QFrame#BubbleUser { background-color: #89b4fa; border-radius: 15px; border-bottom-right-radius: 2px; }
QLabel#BubbleTextUser { color: #1e1e2e; font-weight: 500; }
"""


# --- 线程: 获取模型 ---
class ModelFetcher(QThread):
    success_signal = pyqtSignal(list)
    error_signal = pyqtSignal(str)

    def __init__(self, api_key):
        super().__init__()
        self.api_key = api_key

    def run(self):
        try:
            client = genai.Client(api_key=self.api_key)
            pager = client.models.list()
            valid_models = []

            for m in pager:
                # 只要名字里带 gemini 就算有效
                if hasattr(m, 'name') and "gemini" in m.name.lower():
                    clean_name = m.name.replace("models/", "")
                    valid_models.append(clean_name)

            # 排序优化：Flash > Pro > 其他
            valid_models.sort(key=lambda x: (not "flash" in x, not "pro" in x, x))

            if not valid_models: valid_models = ["gemini-1.5-flash", "gemini-1.5-pro"]
            self.success_signal.emit(valid_models)
        except Exception as e:
            self.error_signal.emit(str(e))


# --- 线程: 发送消息 ---
class GeminiWorker(QThread):
    finished_signal = pyqtSignal(str, str)
    error_signal = pyqtSignal(str)
    session_created_signal = pyqtSignal(object)

    def __init__(self, api_key, model_name, user_text, image_path, chat_session):
        super().__init__()
        self.api_key = api_key
        self.model_name = model_name
        self.user_text = user_text
        self.image_path = image_path
        self.chat_session = chat_session

    def run(self):
        try:
            client = genai.Client(api_key=self.api_key)
            response_text = ""

            if self.image_path:
                img = Image.open(self.image_path)
                response = client.models.generate_content(
                    model=self.model_name,
                    contents=[self.user_text, img]
                )
                response_text = response.text
            else:
                if self.chat_session is None:
                    self.chat_session = client.chats.create(model=self.model_name)
                    self.session_created_signal.emit(self.chat_session)
                response = self.chat_session.send_message(self.user_text)
                response_text = response.text

            self.finished_signal.emit("Gemini", response_text)
        except Exception as e:
            err = str(e)
            if "429" in err: err = "❌ 额度耗尽 (429): 请切换至 gemini-1.5-flash"
            self.error_signal.emit(err)


# --- UI组件 ---
class ChatBubble(QWidget):
    def __init__(self, text, role, image_path=None):
        super().__init__()
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 5, 10, 5)
        self.setLayout(layout)

        bubble_frame = QFrame()
        bubble_layout = QVBoxLayout()
        bubble_layout.setContentsMargins(15, 10, 15, 10)
        bubble_frame.setLayout(bubble_layout)

        if image_path:
            img_label = QLabel()
            pixmap = QPixmap(image_path).scaledToWidth(300, Qt.TransformationMode.SmoothTransformation)
            img_label.setPixmap(pixmap)
            bubble_layout.addWidget(img_label)

        text_label = QLabel(text)
        text_label.setWordWrap(True)
        text_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        if "```" in text: text_label.setFont(QFont("Consolas", 10))
        bubble_layout.addWidget(text_label)

        if role == "User":
            layout.addStretch()
            layout.addWidget(bubble_frame)
            bubble_frame.setObjectName("BubbleUser")
            text_label.setObjectName("BubbleTextUser")
        else:
            layout.addWidget(bubble_frame)
            layout.addStretch()
            bubble_frame.setObjectName("BubbleAI")
        bubble_frame.setMaximumWidth(600)


class GeminiClient(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gemini 桌面版")
        self.resize(950, 750)
        self.chat_session_obj = None
        self.current_image_path = None
        self.setStyleSheet(STYLESHEET)

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        self.main_layout = QVBoxLayout(main_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self.setup_ui()
        self.load_config()
        self.add_message("System", "欢迎使用。")
        if self.api_input.text(): self.refresh_models()

    def setup_ui(self):
        # Top Bar
        top_bar = QFrame()
        top_bar.setObjectName("TopBar")
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(20, 15, 20, 15)

        self.api_input = QLineEdit()
        self.api_input.setPlaceholderText("API Key")
        self.api_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_input.setFixedWidth(260)

        self.refresh_btn = QPushButton("↺")
        self.refresh_btn.setObjectName("RefreshBtn")
        self.refresh_btn.setToolTip("刷新模型列表")
        self.refresh_btn.clicked.connect(self.refresh_models)

        self.model_combo = QComboBox()
        self.model_combo.setPlaceholderText("模型加载中...")
        self.model_combo.setFixedWidth(240)
        self.model_combo.currentIndexChanged.connect(self.reset_chat)

        reset_btn = QPushButton("新对话")
        reset_btn.clicked.connect(self.reset_chat)

        top_layout.addWidget(QLabel("Key:"))
        top_layout.addWidget(self.api_input)
        top_layout.addWidget(self.refresh_btn)
        top_layout.addSpacing(15)
        top_layout.addWidget(self.model_combo)
        top_layout.addStretch()
        top_layout.addWidget(reset_btn)
        self.main_layout.addWidget(top_bar)

        # Chat Area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.chat_widget = QWidget()
        self.chat_widget.setObjectName("ChatContent")
        self.chat_layout = QVBoxLayout(self.chat_widget)
        self.chat_layout.addStretch()
        self.chat_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_area.setWidget(self.chat_widget)
        self.main_layout.addWidget(self.scroll_area)

        # Input Area
        input_frame = QFrame()
        input_frame.setObjectName("InputArea")
        input_layout = QVBoxLayout(input_frame)
        input_layout.setContentsMargins(20, 10, 20, 20)

        # Image Preview
        self.img_preview_box = QWidget()
        self.img_preview_box.setVisible(False)
        img_layout = QHBoxLayout(self.img_preview_box)
        img_layout.setContentsMargins(0, 0, 0, 0)
        self.img_label = QLabel()
        close_img = QPushButton("×")
        close_img.setFixedSize(20, 20)
        close_img.setStyleSheet("background-color: #ff5555; color: white; border-radius: 10px; border:none;")
        close_img.clicked.connect(self.clear_image)
        img_layout.addWidget(QLabel("图片附件:"))
        img_layout.addWidget(self.img_label)
        img_layout.addWidget(close_img)
        img_layout.addStretch()
        input_layout.addWidget(self.img_preview_box)

        # Controls
        row = QHBoxLayout()
        self.upload_btn = QPushButton("📷")
        self.upload_btn.setFixedWidth(40)
        self.upload_btn.clicked.connect(self.select_image)

        self.text_input = QTextEdit()
        self.text_input.setPlaceholderText("输入消息... (Shift+Enter 换行)")
        self.text_input.setFixedHeight(50)
        self.text_input.textChanged.connect(
            lambda: self.text_input.setFixedHeight(min(100, int(self.text_input.document().size().height()) + 10)))

        self.send_btn = QPushButton("发送")
        self.send_btn.setObjectName("SendBtn")
        self.send_btn.setFixedSize(80, 40)
        self.send_btn.clicked.connect(self.send_message)

        row.addWidget(self.upload_btn)
        row.addWidget(self.text_input)
        row.addWidget(self.send_btn)
        input_layout.addLayout(row)
        self.main_layout.addWidget(input_frame)

    # Logic
    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    self.api_input.setText(json.load(f).get("api_key", ""))
            except:
                pass

    def save_config(self):
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump({"api_key": self.api_input.text().strip()}, f)
        except:
            pass

    def refresh_models(self):
        key = self.api_input.text().strip()
        if not key: return
        self.refresh_btn.setEnabled(False)
        self.model_combo.clear()
        self.model_combo.addItem("加载中...")
        self.fetcher = ModelFetcher(key)
        self.fetcher.success_signal.connect(self.on_models_ok)
        self.fetcher.error_signal.connect(self.on_models_fail)
        self.fetcher.start()

    def on_models_ok(self, models):
        self.refresh_btn.setEnabled(True)
        self.model_combo.clear()
        self.model_combo.addItems(models)
        self.add_message("System", f"✅ 已更新模型列表 ({len(models)}个)")
        self.save_config()

    def on_models_fail(self, err):
        self.refresh_btn.setEnabled(True)
        self.model_combo.clear()
        self.model_combo.addItem("gemini-1.5-flash")
        self.add_message("System", f"⚠️ 获取模型失败，已使用默认配置。")

    def select_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "选图", "", "Images (*.png *.jpg *.webp)")
        if path:
            self.current_image_path = path
            self.img_label.setPixmap(QPixmap(path).scaledToHeight(30))
            self.img_preview_box.setVisible(True)

    def clear_image(self):
        self.current_image_path = None
        self.img_preview_box.setVisible(False)

    def reset_chat(self):
        self.chat_session_obj = None
        while self.chat_layout.count() > 1:
            item = self.chat_layout.itemAt(0)
            if item.widget():
                item.widget().setParent(None)
            else:
                self.chat_layout.removeItem(item)
        if self.model_combo.count() > 0:
            self.add_message("System", f"已切换: {self.model_combo.currentText()}")

    def add_message(self, role, text, image_path=None):
        bubble = ChatBubble(text, role, image_path)
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, bubble)
        QApplication.processEvents()
        self.scroll_area.verticalScrollBar().setValue(self.scroll_area.verticalScrollBar().maximum())

    def send_message(self):
        key = self.api_input.text().strip()
        msg = self.text_input.toPlainText().strip()
        if not key: return self.add_message("System", "❌ 请输入 Key")
        if "加载中" in self.model_combo.currentText(): return self.add_message("System", "❌ 请先刷新模型")

        self.save_config()
        if not msg and not self.current_image_path: return

        self.add_message("User", msg, self.current_image_path)
        self.text_input.clear()
        self.send_btn.setEnabled(False)

        path = self.current_image_path
        self.clear_image()

        self.worker = GeminiWorker(key, self.model_combo.currentText(), msg, path, self.chat_session_obj)
        self.worker.finished_signal.connect(lambda r, t: (self.add_message(r, t), self.send_btn.setEnabled(True)))
        self.worker.error_signal.connect(lambda e: (self.add_message("System", e), self.send_btn.setEnabled(True),
                                                    setattr(self, 'chat_session_obj', None)))
        self.worker.session_created_signal.connect(lambda s: setattr(self, 'chat_session_obj', s))
        self.worker.start()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Microsoft YaHei", 10))
    win = GeminiClient()
    win.show()
    sys.exit(app.exec())