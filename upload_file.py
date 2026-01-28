import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox, ttk
import os
import shutil
import subprocess
import re
from datetime import datetime
import platform
import logging
import requests
from io import BytesIO
from PIL import Image, ImageTk
import docx
from http.cookies import SimpleCookie
import time

# ========== 固定配置（对应Go的const） ==========
# 写死的配置常量
IMG_DIR = "imgs"
DOC_FILE_DIR = "docFiles"
# 默认Cookie（对应Go的默认值）
DEFAULT_COOKIE = "Path=/;"
# URL模板默认值（对应Go的Url常量）
DEFAULT_URL = "https://sleye-mobile.lottery.cn/api/jk/uploadImage?gameName=%s&faceAmount=%s"


# ========== 工具函数模块 ==========
class MyFunc:
    """工具函数类，对应Go的myFunc包"""

    def __init__(self, cookie, url_template):
        # 内存中的配置（不再从文件读取）
        self.cookie = cookie
        self.url_template = url_template
        self.img_dir = IMG_DIR
        self.doc_file_dir = DOC_FILE_DIR

        # 确保目录存在
        os.makedirs(self.img_dir, exist_ok=True)
        os.makedirs(self.doc_file_dir, exist_ok=True)

        # 配置日志
        logging.basicConfig(
            format='%(asctime)s %(filename)s:%(lineno)d %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            level=logging.INFO
        )
        self.logger = logging.getLogger(__name__)

    # 更新Cookie（直接修改内存）
    def update_cookie(self, new_cookie):
        self.cookie = new_cookie.strip() or DEFAULT_COOKIE
        self.logger.info(f"Cookie已更新: {self.cookie[:20]}...")  # 只显示前20个字符，保护隐私

    # 更新URL模板
    def update_url_template(self, new_url):
        self.url_template = new_url.strip() or DEFAULT_URL
        self.logger.info(f"URL模板已更新: {self.url_template}")

    def read_dir(self):
        """读取目录中所有图片文件生成文件列表"""
        try:
            files = os.listdir(self.img_dir)
            file_infos = []
            for file in files:
                file_path = os.path.join(self.img_dir, file)
                if os.path.isfile(file_path):
                    file_stat = os.stat(file_path)
                    file_infos.append({
                        "name": file,
                        "path": file_path,
                        "size": file_stat.st_size,
                        "mtime": file_stat.st_mtime
                    })
            return file_infos, None
        except Exception as e:
            self.logger.error(f"读取目录失败: {e}")
            return None, str(e)

    def post_file(self, file_info):
        """上传文件的接口（对应Go的PostFile函数）"""
        try:
            # 获取上传URL
            url = self.get_file_name_url(file_info["name"])
            if not url:
                return "文件名称异常", None  # 修改：返回(错误信息, 响应内容)

            # 打开文件
            file_path = os.path.join(self.img_dir, file_info["name"])
            with open(file_path, 'rb') as file:
                # 构建multipart/form-data请求
                files = {
                    'image': (file_info["name"], file, 'image/png')
                }

                # 设置Cookie
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Mobile Safari/537.36 Edg/143.0.0.0',
                    'Cookie': self.cookie  # ← 直接使用你的完整 Cookie 字符串
                }

                # 发送POST请求
                response = requests.post(
                    url,
                    files=files,
                    headers=headers
                )

                response_text = response.text[:500]  # 截断过长响应，避免弹窗溢出
                self.logger.info(f"{file_info['name']} 上传响应: {response_text}...")
                print(f"{file_info['name']}  {response_text}")
                return None, response_text  # 修改：返回(None, 响应内容)
        except Exception as e:
            self.logger.error(f"上传文件失败: {e}")
            return str(e), None  # 修改：返回(错误信息, None)

    def get_file_bytes(self, file_name, file_size):
        """通过文件名称和文件路径获取文件字节"""
        try:
            file_path = os.path.join(self.img_dir, file_name)
            with open(file_path, 'rb') as file:
                data = file.read(file_size)
            return data, None
        except Exception as e:
            self.logger.error(f"读取文件字节失败: {e}")
            return None, str(e)

    def get_file_name_url(self, file_name):
        """通过文件名称获取url"""
        try:
            # 去掉.png后缀
            file_name = file_name.strip().replace(".png", "")
            name_arr = file_name.split("-")
            if len(name_arr) != 2:
                return ""

            # 替换空格为+
            name = name_arr[0].replace(" ", "+")
            # 格式化URL
            return self.url_template % (name, name_arr[1])
        except Exception as e:
            self.logger.error(f"生成URL失败: {e}")
            return ""

    def set_cookie_raw(self):
        """cookie字符串转requests可用的cookies对象"""
        cookie_raw = self.cookie
        cookie = SimpleCookie()
        cookie.load(cookie_raw)

        # 转换为requests可用的字典格式
        cookies = {}
        for key, morsel in cookie.items():
            cookies[key] = morsel.value
        return cookies

    def get_file_imgs(self, file_name, file_size):
        """从Word文件中提取图片"""
        try:
            file_path = os.path.join(self.doc_file_dir, file_name)
            doc = docx.Document(file_path)

            images = []
            # 提取文档中的所有图片
            for rel in doc.part.rels.values():
                if "image" in rel.target_ref:
                    # 获取图片数据
                    image_data = rel.target_part.blob
                    # 获取图片格式
                    if rel.target_ref.endswith('.jpeg') or rel.target_ref.endswith('.jpg'):
                        img_format = "jpeg"
                    elif rel.target_ref.endswith('.png'):
                        img_format = "png"
                    else:
                        img_format = "unknown"

                    images.append({
                        "format": img_format,
                        "data": image_data,
                        "path": rel.target_ref,
                        "size": len(image_data)
                    })

            return images, None
        except Exception as e:
            self.logger.error(f"提取Word图片失败: {e}")
            return None, str(e)

    def get_file_img_first(self, images):
        """提取第一个jpeg图片"""
        for img in images:
            if img["format"] == "jpeg":
                return img, True
        return {}, False

    def compress(self, buf):
        """图片大小调整压缩"""
        try:
            width = 50
            height = 70

            # 解码图片
            img = Image.open(BytesIO(buf))
            # 调整大小（使用LANCZOS滤波器，对应Go的Lanczos3）
            resized_img = img.resize((width, height), Image.Resampling.LANCZOS)

            # 重新编码
            new_buf = BytesIO()
            img_format = img.format.lower()

            if img_format == "png":
                resized_img.save(new_buf, format='PNG')
            elif img_format in ["jpeg", "jpg"]:
                resized_img.save(new_buf, format='JPEG', quality=100)
            else:
                return None, "该图片格式不支持压缩"

            # 如果压缩后更小则使用压缩后的
            compressed_data = new_buf.getvalue()
            if len(compressed_data) < len(buf):
                return compressed_data, None
            else:
                return buf, None
        except Exception as e:
            self.logger.error(f"图片压缩失败: {e}")
            return None, str(e)

    def save_img(self, file_name, file_byte):
        """存入图片到指定目录"""
        try:
            file_path = os.path.join(self.img_dir, file_name)
            with open(file_path, 'wb') as out_file:
                out_file.write(file_byte)
            return None
        except Exception as e:
            self.logger.error(f"保存图片失败: {e}")
            return str(e)

    def get_img_name_from_file(self, file_name):
        """从文件名获取图片名称"""
        try:
            file_name_arr = file_name.split("元 ")
            if len(file_name_arr) != 2:
                self.logger.error(f"fileName: {file_name} fileNameArr: {file_name_arr}")
                return "", "文件格式名字解析出错1！"

            index_begin = file_name_arr[0].find(" ")
            if index_begin == -1:
                return "", "文件格式名字解析出错2！"

            # 分割字符串数组
            temp_arr = list(file_name_arr[0])
            file_name_total_arr = temp_arr[index_begin + 1:]

            return self.split_str_and_num(file_name_total_arr)
        except Exception as e:
            self.logger.error(f"解析图片名称失败: {e}")
            return "", str(e)

    def split_str_and_num(self, str_arr):
        """获取字符串中的最后一个完整数字"""
        try:
            index = -1
            l = len(str_arr)

            # 从后往前找第一个非数字字符
            for i in range(l - 1, -1, -1):
                if not self.is_num(str_arr[i]):
                    index = i + 1
                    break

            if index == l or index <= 0:
                return "", "文件名字格式错误！"

            # 分割字符串和数字
            st = ''.join(str_arr[:index]).strip()
            in_str = ''.join(str_arr[index:])

            return f"{st}-{in_str}.png", None
        except Exception as e:
            self.logger.error(f"分割字符串和数字失败: {e}")
            return "", str(e)

    def is_num(self, s):
        """判断某个字符是否是数字"""
        return s in ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"]


# ========== 图片提取处理器 ==========
class ExtractFileProcessor:
    """图片提取处理器（对应extractFile.go）"""

    def __init__(self, my_func, app):
        self.my_func = my_func
        self.app = app  # 引用主应用用于日志输出

    def process(self):
        """执行图片提取处理"""
        try:
            self.app.add_log("开始执行图片提取处理...")

            # 读取文档目录
            if not os.path.exists(self.my_func.doc_file_dir):
                self.app.add_log(f"文档目录不存在: {self.my_func.doc_file_dir}")
                return "文档目录不存在"

            # 获取目录中的所有文件
            files = os.listdir(self.my_func.doc_file_dir)
            if not files:
                self.app.add_log("文档目录中没有文件")
                return "文档目录中没有文件"

            # 处理每个文件
            for file_name in files:
                file_path = os.path.join(self.my_func.doc_file_dir, file_name)
                if os.path.isdir(file_path):
                    continue

                # 获取文件大小
                file_size = os.path.getsize(file_path)
                self.app.add_log(f"开始处理文件: {file_name} (大小: {file_size} bytes)")

                # 提取图片
                images, err = self.my_func.get_file_imgs(file_name, file_size)
                if err:
                    self.app.add_log(f"提取图片失败: {err}")
                    return err

                if not images:
                    self.app.add_log(f"文件 {file_name} 中未找到图片")
                    continue

                # 获取第一个jpeg图片
                img, ok = self.my_func.get_file_img_first(images)
                if ok:
                    self.app.add_log(f"找到JPEG图片，开始处理...")

                    # 压缩图片
                    new_img, err = self.my_func.compress(img["data"])
                    if err:
                        self.app.add_log(f"图片压缩失败: {err}")
                        return err

                    # 获取图片名称
                    img_name, err = self.my_func.get_img_name_from_file(file_name)
                    if err:
                        self.app.add_log(f"获取图片名称失败: {err}")
                        return err

                    # 保存图片
                    err = self.my_func.save_img(img_name, new_img)
                    if err:
                        self.app.add_log(f"保存图片失败: {err}")
                        return err

                    self.app.add_log(f"图片已保存: {img_name}")
                else:
                    self.app.add_log(f"文件 {file_name} 获取图片失败!")

            self.app.add_log("图片转换获取完成！")
            return "图片转换获取完成！"
        except Exception as e:
            self.app.add_log(f"处理失败: {str(e)}")
            return str(e)


# ========== 上传文件处理器 ==========
class UploadFileProcessor:
    """文件上传处理器（对应uploadFile.go）"""

    def __init__(self, my_func, app):
        self.my_func = my_func
        self.app = app  # 引用主应用用于日志输出

    def process(self):
        """执行文件上传处理"""
        try:
            self.app.add_log("开始执行文件上传处理...")

            # 检查图片目录是否存在
            if not os.path.exists(self.my_func.img_dir):
                self.app.add_log(f"图片目录不存在: {self.my_func.img_dir}")
                return "图片目录不存在", ""

            # 读取图片目录中的所有文件
            files, err = self.my_func.read_dir()
            if err:
                self.app.add_log(f"读取图片目录失败: {err}")
                return f"读取图片目录失败: {err}", ""

            if not files:
                self.app.add_log("图片目录中没有文件可上传")
                return "图片目录中没有文件可上传", ""

            self.app.add_log(f"找到 {len(files)} 个文件待上传")

            # 收集每个文件的上传结果和响应
            upload_results = []
            has_error = False

            # 逐个上传文件
            for idx, file_info in enumerate(files):
                filename = file_info['name']
                self.app.add_log(f"[{idx + 1}/{len(files)}] 开始上传文件: {filename}")

                # 执行上传（接收错误和响应）
                err, response_text = self.my_func.post_file(file_info)

                if err:
                    has_error = True
                    error_msg = f"[{idx + 1}/{len(files)}] {filename} 上传失败: {err}"
                    self.app.add_log(error_msg)
                    upload_results.append(error_msg)
                else:
                    # 记录接口响应
                    resp_msg = f"[{idx + 1}/{len(files)}] {filename} 接口响应:\n{response_text}"
                    self.app.add_log(resp_msg)
                    upload_results.append(resp_msg)

                # 模拟Go中的time.Sleep(1 * time.Second)
                if idx < len(files) - 1:  # 最后一个文件不需要等待
                    self.app.add_log("等待1秒后继续上传下一个文件...")
                    time.sleep(1)

            # 汇总结果
            result_summary = "上传处理完成（请查看接口响应判断是否成功）"
            response_summary = "\n\n".join(upload_results)

            self.app.add_log(result_summary)
            return result_summary, response_summary
        except Exception as e:
            error_msg = f"上传处理失败: {str(e)}"
            self.app.add_log(error_msg)
            return error_msg, ""


# ========== 主应用程序 ==========
class FileUploadTool:
    """文件上传工具 - 纯Python版本（内存配置版）"""

    def __init__(self, root_window):
        self.root = root_window
        self.root.title("文件上传工具 - Python内存配置版")
        self.root.geometry("1030x900")
        self.root.resizable(True, True)

        self.font = ("SimHei", 10)
        self.title_font = ("SimHei", 12, "bold")

        self.imgs_old_dir = "imgsOld"
        os.makedirs(self.imgs_old_dir, exist_ok=True)

        self.my_func = MyFunc(DEFAULT_COOKIE, DEFAULT_URL)
        self.extract_processor = ExtractFileProcessor(self.my_func, self)
        self.upload_processor = UploadFileProcessor(self.my_func, self)

        # ===== 滚动容器 =====
        scroll_container = ttk.Frame(self.root)
        scroll_container.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(scroll_container, borderwidth=0, background="#ffffff")

        self.scrollbar = ttk.Scrollbar(scroll_container, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)

        # 当内容变化时调整 Canvas 宽度和滚动区域
        def on_frame_configure(event):
            # 获取内容的实际宽度
            content_width = event.width
            # 限制 Canvas 宽度不超过窗口宽度
            max_width = self.root.winfo_width() - self.scrollbar.winfo_width()
            canvas_width = min(content_width, max_width)
            # 设置 Canvas 宽度
            self.canvas.config(width=canvas_width)
            # 设置滚动区域
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))

        self.scrollable_frame.bind("<Configure>", on_frame_configure)

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        # grid 布局，让滚动条紧贴内容
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.grid(row=0, column=1, sticky="ns")

        scroll_container.grid_rowconfigure(0, weight=1)
        scroll_container.grid_columnconfigure(0, weight=1)

        # ===== 鼠标滚轮支持 =====
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Button-4>", self._on_mousewheel)
        self.canvas.bind_all("<Button-5>", self._on_mousewheel)

        # ===== 所有内容放到 scrollable_frame 中 =====
        main_container = ttk.Frame(self.scrollable_frame, padding="10")
        main_container.pack(fill=tk.BOTH, expand=True)

        top_notebook_frame = ttk.Frame(main_container)
        top_notebook_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=(0, 10))

        preview_frame = ttk.LabelFrame(main_container, text="实时目录预览", padding="10")
        preview_frame.pack(fill=tk.BOTH, expand=True)

        self.main_frame = ttk.Frame(top_notebook_frame)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        self.tab_control = ttk.Notebook(self.main_frame)
        self.tab_control.pack(fill=tk.BOTH, expand=True)

        self.config_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.config_tab, text="配置")

        self.file_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.file_tab, text="文件管理")

        self.action_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.action_tab, text="操作")

        self.log_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.log_tab, text="日志")

        self.init_config_tab()
        self.init_file_tab()
        self.init_action_tab()
        self.init_log_tab()

        self.init_real_time_preview(preview_frame)

        self.logs = []
        self.add_log("应用程序已启动（Python内存配置版）")
        self.refresh_file_list()
        self.refresh_real_time_preview()
        self.auto_refresh_preview()

    def _on_mousewheel(self, event):
        if event.delta:
            self.canvas.yview_scroll(-1 * (event.delta // 120), "units")
        else:
            if event.num == 4:
                self.canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                self.canvas.yview_scroll(1, "units")

    def init_config_tab(self):
        """初始化配置标签页（内存配置版）"""
        # Cookie配置区域
        cookie_frame = ttk.LabelFrame(self.config_tab, text="Cookie配置（内存版）", padding="10")
        cookie_frame.pack(fill=tk.X, pady=10, padx=10)

        # Cookie标签
        ttk.Label(cookie_frame, text="Cookie值:", font=self.font).grid(row=0, column=0, sticky=tk.W, pady=5)

        # Cookie输入框（多行）
        self.cookie_text = tk.Text(cookie_frame, width=80, height=8, font=self.font)
        self.cookie_text.grid(row=1, column=0, columnspan=2, sticky=tk.W + tk.E, pady=5)
        # 填充默认值
        self.cookie_text.insert(1.0, DEFAULT_COOKIE)

        # 应用Cookie按钮（直接修改内存）
        apply_cookie_btn = ttk.Button(cookie_frame, text="应用Cookie", command=self.apply_cookie)
        apply_cookie_btn.grid(row=2, column=0, sticky=tk.W, pady=10)

        # 重置Cookie按钮
        reset_cookie_btn = ttk.Button(cookie_frame, text="重置为默认", command=self.reset_cookie)
        reset_cookie_btn.grid(row=2, column=1, sticky=tk.W, pady=10, padx=5)

        # URL配置区域
        url_frame = ttk.LabelFrame(self.config_tab, text="上传接口URL配置", padding="10")
        url_frame.pack(fill=tk.X, pady=10, padx=10)

        # URL标签
        ttk.Label(url_frame, text="URL模板:", font=self.font).grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Label(url_frame, text="(使用 %s 作为gameName和faceAmount的占位符)", font=("SimHei", 9),
                  foreground="gray").grid(row=1, column=0, sticky=tk.W)

        # URL输入框
        self.url_var = tk.StringVar(value=DEFAULT_URL)
        url_entry = ttk.Entry(url_frame, textvariable=self.url_var, width=80, font=self.font)
        url_entry.grid(row=0, column=1, sticky=tk.W + tk.E, pady=5, padx=5)

        # 应用URL按钮
        apply_url_btn = ttk.Button(url_frame, text="应用URL模板", command=self.apply_url_template)
        apply_url_btn.grid(row=0, column=2, sticky=tk.W, pady=5, padx=5)

        # 重置URL按钮
        reset_url_btn = ttk.Button(url_frame, text="重置为默认", command=self.reset_url_template)
        reset_url_btn.grid(row=1, column=2, sticky=tk.W, pady=5, padx=5)

        # 固定配置显示区域
        config_frame = ttk.LabelFrame(self.config_tab, text="固定配置（不可修改）", padding="10")
        config_frame.pack(fill=tk.X, pady=10, padx=10)

        # 显示固定配置
        ttk.Label(config_frame, text=f"图片目录: {IMG_DIR}", font=self.font).grid(row=0, column=0, sticky=tk.W, pady=3)
        ttk.Label(config_frame, text=f"文档目录: {DOC_FILE_DIR}", font=self.font).grid(row=1, column=0, sticky=tk.W,
                                                                                       pady=3)
        ttk.Label(config_frame, text=f"图片备份目录: {self.imgs_old_dir}", font=self.font).grid(row=2, column=0,
                                                                                                sticky=tk.W, pady=3)

    def init_file_tab(self):
        """初始化文件管理标签页"""
        # 文件管理区域
        file_frame = ttk.LabelFrame(self.file_tab, text="文件管理", padding="10")
        file_frame.pack(fill=tk.BOTH, expand=True, pady=10, padx=10)

        # 文件路径标签
        ttk.Label(file_frame, text="选择文件:", font=self.font).grid(row=0, column=0, sticky=tk.W, pady=5)

        # 文件路径输入框
        self.file_path_var = tk.StringVar()
        file_entry = ttk.Entry(file_frame, textvariable=self.file_path_var, width=60, font=self.font)
        file_entry.grid(row=0, column=1, sticky=tk.W + tk.E, pady=5, padx=5)

        # 浏览文件按钮
        browse_btn = ttk.Button(file_frame, text="浏览", command=self.browse_file)
        browse_btn.grid(row=0, column=2, sticky=tk.W, pady=5, padx=5)

        # 文件操作按钮
        btn_frame = ttk.Frame(file_frame)
        btn_frame.grid(row=0, column=3, sticky=tk.W, pady=5, padx=5)

        # 清空文档目录按钮
        clear_doc_btn = ttk.Button(btn_frame, text="清空文档目录", command=self.clear_doc_directory)
        clear_doc_btn.pack(side=tk.TOP, pady=2)

        # 移动图片到备份目录按钮
        move_img_btn = ttk.Button(btn_frame, text="移动图片到备份", command=self.move_images_to_backup)
        move_img_btn.pack(side=tk.TOP, pady=2)

        # 复制选中文件按钮（已修改为复制）
        move_file_btn = ttk.Button(btn_frame, text="复制选中文件", command=self.move_selected_file)
        move_file_btn.pack(side=tk.TOP, pady=2)

        # 拖放区域
        drop_frame = ttk.LabelFrame(file_frame, text="拖放文件到此处", padding="20")
        drop_frame.grid(row=1, column=0, columnspan=4, sticky=tk.NSEW, pady=10)

        # 使框架可扩展
        file_frame.columnconfigure(1, weight=1)
        file_frame.rowconfigure(1, weight=1)

        # 拖放区域文本
        self.drop_text = tk.StringVar()
        self.drop_text.set("请拖放文件到此处，或使用上方的浏览按钮选择文件")
        drop_label = ttk.Label(drop_frame, textvariable=self.drop_text, font=self.font, justify=tk.CENTER)
        drop_label.pack(expand=True)

    def init_action_tab(self):
        """初始化操作标签页"""
        # 操作区域
        action_frame = ttk.LabelFrame(self.action_tab, text="执行操作", padding="20")
        action_frame.pack(fill=tk.BOTH, expand=True, pady=10, padx=10)

        # 按钮容器
        btn_container = ttk.Frame(action_frame)
        btn_container.pack(pady=20)

        # 执行解析文件按钮
        extract_btn = ttk.Button(btn_container, text="执行解析文件", command=self.execute_extract_file, width=30)
        extract_btn.pack(side=tk.LEFT, padx=10)

        # 执行上传文件按钮
        upload_btn = ttk.Button(btn_container, text="执行上传文件", command=self.execute_upload_file, width=30)
        upload_btn.pack(side=tk.LEFT, padx=10)

        # 操作说明
        instructions = self._get_operation_instructions()
        instructions_text = scrolledtext.ScrolledText(action_frame, wrap=tk.WORD, width=80, height=15, font=self.font)
        instructions_text.pack(fill=tk.BOTH, expand=True, pady=10)
        instructions_text.insert(tk.END, instructions)
        instructions_text.config(state=tk.DISABLED)

    def init_log_tab(self):
        """初始化日志标签页"""
        # 日志区域
        log_frame = ttk.LabelFrame(self.log_tab, text="操作日志", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=10, padx=10)

        # 日志文本框
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, width=80, height=25, font=self.font)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.config(state=tk.DISABLED)

        # 清空日志按钮
        clear_log_btn = ttk.Button(log_frame, text="清空日志", command=self.clear_logs)
        clear_log_btn.pack(side=tk.RIGHT, pady=5)

    def init_real_time_preview(self, parent_frame):
        """初始化实时目录预览区域（核心新增功能）"""
        # 分割为图片目录和文档目录两个面板
        img_frame = ttk.LabelFrame(parent_frame, text=f"图片目录 ({IMG_DIR})", padding="5")
        img_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        doc_frame = ttk.LabelFrame(parent_frame, text=f"文档目录 ({DOC_FILE_DIR})", padding="5")
        doc_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))

        # ========== 图片目录预览 ==========
        # 顶部控制栏
        img_ctrl_frame = ttk.Frame(img_frame)
        img_ctrl_frame.pack(fill=tk.X, pady=5)

        ttk.Label(img_ctrl_frame, text="文件列表:", font=self.font).pack(side=tk.LEFT)
        ttk.Button(img_ctrl_frame, text="刷新", command=lambda: self.refresh_real_time_preview("img")).pack(
            side=tk.LEFT, padx=5)
        ttk.Button(img_ctrl_frame, text="打开目录", command=lambda: self.open_directory(IMG_DIR)).pack(
            side=tk.LEFT, padx=5)

        # 文件统计信息
        self.img_stats_var = tk.StringVar(value="文件数: 0 | 总大小: 0 KB")
        ttk.Label(img_ctrl_frame, textvariable=self.img_stats_var, font=self.font).pack(side=tk.RIGHT)

        # 文件列表
        img_list_frame = ttk.Frame(img_frame)
        img_list_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        # 图片文件列表树视图（调整高度为12行）
        img_columns = ("name", "size", "mtime")
        self.img_tree = ttk.Treeview(img_list_frame, columns=img_columns, show="headings", height=12)
        self.img_tree.heading("name", text="文件名")
        self.img_tree.heading("size", text="大小(KB)")
        self.img_tree.heading("mtime", text="修改时间")
        self.img_tree.column("name", width=200, anchor=tk.W)
        self.img_tree.column("size", width=80, anchor=tk.CENTER)
        self.img_tree.column("mtime", width=120, anchor=tk.CENTER)

        # 滚动条
        img_scroll_y = ttk.Scrollbar(img_list_frame, orient=tk.VERTICAL, command=self.img_tree.yview)
        img_scroll_x = ttk.Scrollbar(img_list_frame, orient=tk.HORIZONTAL, command=self.img_tree.xview)
        self.img_tree.configure(yscrollcommand=img_scroll_y.set, xscrollcommand=img_scroll_x.set)

        # 布局
        self.img_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        img_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        img_scroll_x.pack(side=tk.BOTTOM, fill=tk.X)

        # 图片预览区域
        img_preview_frame = ttk.LabelFrame(img_frame, text="图片预览", padding="5")
        img_preview_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.img_preview_label = ttk.Label(img_preview_frame, text="选择图片文件查看预览", font=self.font)
        self.img_preview_label.pack(expand=True)

        # 绑定图片选择事件
        self.img_tree.bind("<<TreeviewSelect>>", self.on_img_select)
        self.img_tree.bind("<Double-1>", lambda e: self.on_file_double_click_custom(IMG_DIR, e))

        # ========== 文档目录预览 ==========
        # 顶部控制栏
        doc_ctrl_frame = ttk.Frame(doc_frame)
        doc_ctrl_frame.pack(fill=tk.X, pady=5)

        ttk.Label(doc_ctrl_frame, text="文件列表:", font=self.font).pack(side=tk.LEFT)
        ttk.Button(doc_ctrl_frame, text="刷新", command=lambda: self.refresh_real_time_preview("doc")).pack(
            side=tk.LEFT, padx=5)
        ttk.Button(doc_ctrl_frame, text="打开目录", command=lambda: self.open_directory(DOC_FILE_DIR)).pack(
            side=tk.LEFT, padx=5)

        # 文件统计信息
        self.doc_stats_var = tk.StringVar(value="文件数: 0 | 总大小: 0 KB")
        ttk.Label(doc_ctrl_frame, textvariable=self.doc_stats_var, font=self.font).pack(side=tk.RIGHT)

        # 文件列表
        doc_list_frame = ttk.Frame(doc_frame)
        doc_list_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        # 文档文件列表树视图（调整高度为12行）
        doc_columns = ("name", "size", "mtime")
        self.doc_tree = ttk.Treeview(doc_list_frame, columns=doc_columns, show="headings", height=12)
        self.doc_tree.heading("name", text="文件名")
        self.doc_tree.heading("size", text="大小(KB)")
        self.doc_tree.heading("mtime", text="修改时间")
        self.doc_tree.column("name", width=200, anchor=tk.W)
        self.doc_tree.column("size", width=80, anchor=tk.CENTER)
        self.doc_tree.column("mtime", width=120, anchor=tk.CENTER)

        # 滚动条
        doc_scroll_y = ttk.Scrollbar(doc_list_frame, orient=tk.VERTICAL, command=self.doc_tree.yview)
        doc_scroll_x = ttk.Scrollbar(doc_list_frame, orient=tk.HORIZONTAL, command=self.doc_tree.xview)
        self.doc_tree.configure(yscrollcommand=doc_scroll_y.set, xscrollcommand=doc_scroll_x.set)

        # 布局
        self.doc_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        doc_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        doc_scroll_x.pack(side=tk.BOTTOM, fill=tk.X)

        # 文档信息区域
        doc_info_frame = ttk.LabelFrame(doc_frame, text="文件信息", padding="5")
        doc_info_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.doc_info_var = tk.StringVar(value="选择文档文件查看信息")
        doc_info_label = ttk.Label(doc_info_frame, textvariable=self.doc_info_var, font=self.font, wraplength=400)
        doc_info_label.pack(expand=True)

        # 绑定文档选择事件
        self.doc_tree.bind("<<TreeviewSelect>>", self.on_doc_select)
        self.doc_tree.bind("<Double-1>", lambda e: self.on_file_double_click_custom(DOC_FILE_DIR, e))

    def _get_operation_instructions(self):
        """获取操作说明文本"""
        return f"""
        操作说明（即开图片上传）：
        1. 在"配置"标签页中：
           - 输入Cookie值并点击"应用Cookie"（仅内存生效，重启后恢复默认）
           - 配置URL模板并点击"应用URL模板"（支持修改）
           - 图片目录({IMG_DIR})和文档目录({DOC_FILE_DIR})已写死，不可修改

        2. 在"文件管理"标签页中：
           - 选择要处理的文件
           - 点击"清空文档目录"按钮清空{DOC_FILE_DIR}目录
           - 点击"移动图片到备份"按钮将{IMG_DIR}中的图片移动到{self.imgs_old_dir}
           - 点击"复制选中文件"按钮将选择的文件复制到{DOC_FILE_DIR}

        3. 核心操作：
           - 执行解析文件：从{DOC_FILE_DIR}的Word文档中提取图片，压缩后保存到{IMG_DIR}
           - 执行上传文件：从{IMG_DIR}读取所有图片，逐个上传到指定接口（间隔1秒）
           - 上传完成后会显示每个文件的接口响应，需自行判断是否上传成功

        4. 新增功能：
           - 底部"实时目录预览"区域可实时查看{IMG_DIR}和{DOC_FILE_DIR}目录
           - 支持图片预览、文件信息查看、双击打开文件/目录
           - 自动每2秒刷新一次目录内容，也可手动点击刷新按钮

        5. 其他功能：
           - 在"日志"标签页中查看操作日志
           - 右侧面板可实时查看各目录的文件列表
           - Cookie和URL修改仅在当前会话生效，重启程序恢复默认值
        """

    # ========== 新增的实时预览相关方法 ==========
    def refresh_real_time_preview(self, target="all"):
        """刷新实时预览区域"""
        try:
            # 刷新图片目录
            if target == "all" or target == "img":
                self._refresh_img_preview()

            # 刷新文档目录
            if target == "all" or target == "doc":
                self._refresh_doc_preview()

        except Exception as e:
            self.add_log(f"刷新实时预览失败: {str(e)}")

    def _refresh_img_preview(self):
        """刷新图片目录预览"""
        # 清空现有列表
        for item in self.img_tree.get_children():
            self.img_tree.delete(item)

        total_size = 0
        file_count = 0

        # 读取图片目录
        if os.path.exists(IMG_DIR):
            for filename in os.listdir(IMG_DIR):
                file_path = os.path.join(IMG_DIR, filename)
                if os.path.isfile(file_path):
                    # 获取文件信息
                    file_size = os.path.getsize(file_path)
                    file_size_kb = file_size / 1024
                    mtime = os.path.getmtime(file_path)
                    mtime_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")

                    # 插入到树视图
                    self.img_tree.insert("", tk.END, values=(filename, f"{file_size_kb:.1f}", mtime_str),
                                         tags=(file_path,))

                    total_size += file_size
                    file_count += 1

        # 更新统计信息
        total_size_kb = total_size / 1024
        self.img_stats_var.set(f"文件数: {file_count} | 总大小: {total_size_kb:.1f} KB")

    def _refresh_doc_preview(self):
        """刷新文档目录预览"""
        # 清空现有列表
        for item in self.doc_tree.get_children():
            self.doc_tree.delete(item)

        total_size = 0
        file_count = 0

        # 读取文档目录
        if os.path.exists(DOC_FILE_DIR):
            for filename in os.listdir(DOC_FILE_DIR):
                file_path = os.path.join(DOC_FILE_DIR, filename)
                if os.path.isfile(file_path):
                    # 获取文件信息
                    file_size = os.path.getsize(file_path)
                    file_size_kb = file_size / 1024
                    mtime = os.path.getmtime(file_path)
                    mtime_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")

                    # 插入到树视图
                    self.doc_tree.insert("", tk.END, values=(filename, f"{file_size_kb:.1f}", mtime_str),
                                         tags=(file_path,))

                    total_size += file_size
                    file_count += 1

        # 更新统计信息
        total_size_kb = total_size / 1024
        self.doc_stats_var.set(f"文件数: {file_count} | 总大小: {total_size_kb:.1f} KB")

    def on_img_select(self, event):
        """图片文件选择事件"""
        selected_items = self.img_tree.selection()
        if selected_items:
            item = selected_items[0]
            file_path = self.img_tree.item(item, "tags")[0] if self.img_tree.item(item, "tags") else ""
            if file_path and os.path.exists(file_path):
                try:
                    # 加载并预览图片
                    img = Image.open(file_path)
                    # 调整预览尺寸（保持比例）
                    img.thumbnail((300, 300), Image.Resampling.LANCZOS)
                    self.img_thumbnail = ImageTk.PhotoImage(img)
                    self.img_preview_label.config(image=self.img_thumbnail, text="")
                except Exception as e:
                    self.img_preview_label.config(text=f"无法预览图片:\n{str(e)}", image="")
        else:
            self.img_preview_label.config(text="选择图片文件查看预览", image="")

    def on_doc_select(self, event):
        """文档文件选择事件"""
        selected_items = self.doc_tree.selection()
        if selected_items:
            item = selected_items[0]
            file_path = self.doc_tree.item(item, "tags")[0] if self.doc_tree.item(item, "tags") else ""
            if file_path and os.path.exists(file_path):
                try:
                    # 获取文件详细信息
                    file_stat = os.stat(file_path)
                    file_size = file_stat.st_size / 1024
                    mtime = datetime.fromtimestamp(file_stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                    ctime = datetime.fromtimestamp(file_stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S")

                    info_text = f"""
文件名: {os.path.basename(file_path)}
文件路径: {file_path}
文件大小: {file_size:.1f} KB
创建时间: {ctime}
修改时间: {mtime}

文件类型: {self._get_file_type(file_path)}
                    """
                    self.doc_info_var.set(info_text.strip())
                except Exception as e:
                    self.doc_info_var.set(f"获取文件信息失败:\n{str(e)}")
        else:
            self.doc_info_var.set("选择文档文件查看信息")

    def _get_file_type(self, file_path):
        """获取文件类型"""
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".docx":
            return "Word文档 (.docx)"
        elif ext == ".doc":
            return "Word文档 (.doc)"
        elif ext == ".png":
            return "PNG图片"
        elif ext in [".jpg", ".jpeg"]:
            return "JPEG图片"
        else:
            return f"未知类型 ({ext})"

    def open_directory(self, dir_path):
        """打开指定目录"""
        if os.path.exists(dir_path):
            try:
                if platform.system() == "Windows":
                    os.startfile(dir_path)
                elif platform.system() == "Darwin":
                    subprocess.run(["open", dir_path])
                else:
                    subprocess.run(["xdg-open", dir_path])
                self.add_log(f"已打开目录: {dir_path}")
            except Exception as e:
                self.add_log(f"打开目录失败: {str(e)}")
                messagebox.showerror("错误", f"打开目录失败: {str(e)}")
        else:
            messagebox.showwarning("警告", f"目录不存在: {dir_path}")

    def on_file_double_click_custom(self, base_dir, event):
        """自定义双击打开文件事件"""
        tree = event.widget
        selected_items = tree.selection()
        if selected_items:
            item = selected_items[0]
            file_path = tree.item(item, "tags")[0] if tree.item(item, "tags") else ""
            if file_path and os.path.exists(file_path):
                try:
                    # 根据系统打开文件
                    if platform.system() == "Windows":
                        os.startfile(file_path)
                    elif platform.system() == "Darwin":  # macOS
                        subprocess.run(["open", file_path])
                    else:  # Linux
                        subprocess.run(["xdg-open", file_path])
                    self.add_log(f"已打开文件: {file_path}")
                except Exception as e:
                    self.add_log(f"打开文件失败: {str(e)}")
                    messagebox.showerror("错误", f"打开文件失败: {str(e)}")

    def auto_refresh_preview(self):
        """自动刷新预览（每2秒）"""
        self.refresh_real_time_preview()
        # 定时调用自己，实现循环刷新
        self.root.after(2000, self.auto_refresh_preview)

    # ========== 核心执行方法 ==========
    def apply_cookie(self):
        """应用Cookie（直接修改内存）"""
        try:
            cookie_value = self.cookie_text.get(1.0, tk.END).strip()
            if not cookie_value:
                messagebox.showwarning("警告", "Cookie值不能为空，将使用默认值")
                cookie_value = DEFAULT_COOKIE

            # 直接更新内存中的Cookie
            self.my_func.update_cookie(cookie_value)

            # 更新文本框（去除多余空行）
            self.cookie_text.delete(1.0, tk.END)
            self.cookie_text.insert(1.0, cookie_value)

            self.add_log("Cookie已应用（仅内存生效，重启后恢复默认）")
            messagebox.showinfo("成功", "Cookie已应用！（仅当前会话生效）")
        except Exception as e:
            messagebox.showerror("错误", f"应用Cookie失败: {str(e)}")
            self.add_log(f"错误: 应用Cookie失败: {str(e)}")

    def reset_cookie(self):
        """重置Cookie为默认值"""
        self.cookie_text.delete(1.0, tk.END)
        self.cookie_text.insert(1.0, DEFAULT_COOKIE)
        self.my_func.update_cookie(DEFAULT_COOKIE)
        self.add_log("Cookie已重置为默认值")
        messagebox.showinfo("成功", "Cookie已重置为默认值！")

    def apply_url_template(self):
        """应用URL模板"""
        try:
            url_value = self.url_var.get().strip()
            if not url_value:
                messagebox.showwarning("警告", "URL模板不能为空，将使用默认值")
                url_value = DEFAULT_URL

            # 直接更新内存中的URL模板
            self.my_func.update_url_template(url_value)
            self.add_log(f"URL模板已应用: {url_value}")
            messagebox.showinfo("成功", "URL模板已应用！")
        except Exception as e:
            messagebox.showerror("错误", f"应用URL模板失败: {str(e)}")
            self.add_log(f"错误: 应用URL模板失败: {str(e)}")

    def reset_url_template(self):
        """重置URL模板为默认值"""
        self.url_var.set(DEFAULT_URL)
        self.my_func.update_url_template(DEFAULT_URL)
        self.add_log("URL模板已重置为默认值")
        messagebox.showinfo("成功", "URL模板已重置为默认值！")

    def execute_extract_file(self):
        """执行Python版本的图片提取处理"""
        try:
            # 创建进度窗口
            progress_window = tk.Toplevel(self.root)
            progress_window.title("执行中")
            progress_window.geometry("400x100")
            progress_window.transient(self.root)
            progress_window.grab_set()
            ttk.Label(progress_window, text="正在执行解析文件，请稍候...", font=self.font).pack(pady=20)
            progress_window.update()

            # 执行处理
            result = self.extract_processor.process()

            # 关闭进度窗口
            progress_window.destroy()

            # 刷新文件列表和实时预览
            self.refresh_file_list()
            self.refresh_real_time_preview()

            # 显示结果
            if "完成" in result or "成功" in result:
                messagebox.showinfo("成功", f"解析文件执行成功！\n{result}")
            else:
                messagebox.showerror("错误", f"解析文件执行失败:\n{result}")

        except Exception as e:
            messagebox.showerror("错误", f"执行解析文件时出错: {str(e)}")
            self.add_log(f"错误: 执行解析文件时出错: {str(e)}")

    def execute_upload_file(self):
        """执行Python版本的文件上传处理"""
        try:
            # 验证URL配置
            if not self.my_func.url_template:
                messagebox.showwarning("警告", "URL模板未配置，请先在配置页设置")
                return

            # 创建进度窗口
            progress_window = tk.Toplevel(self.root)
            progress_window.title("执行中")
            progress_window.geometry("400x100")
            progress_window.transient(self.root)
            progress_window.grab_set()
            ttk.Label(progress_window, text="正在执行文件上传，请稍候...", font=self.font).pack(pady=20)
            progress_window.update()

            # 执行上传处理（接收汇总信息和响应内容）
            result, response_summary = self.upload_processor.process()

            # 关闭进度窗口
            progress_window.destroy()

            # 刷新文件列表和实时预览
            self.refresh_file_list()
            self.refresh_real_time_preview()

            # 显示结果（包含接口响应）
            full_message = f"{result}\n\n=== 接口响应详情 ===\n{response_summary}"
            messagebox.showinfo("上传处理完成", full_message)

        except Exception as e:
            error_msg = f"执行文件上传时出错: {str(e)}"
            messagebox.showerror("错误", error_msg)
            self.add_log(f"错误: {error_msg}")

    # ========== 辅助方法 ==========
    def get_current_directory(self):
        """获取当前选中的目录路径"""
        dir_type = self.selected_dir.get() if hasattr(self, 'selected_dir') else ""
        if dir_type == "图片目录":
            return IMG_DIR
        elif dir_type == "文档目录":
            return DOC_FILE_DIR
        elif dir_type == "图片备份目录":
            return self.imgs_old_dir
        return ""

    def refresh_file_list(self):
        """刷新原有文件列表"""
        # 兼容原有功能，保留此方法
        pass

    def on_file_select(self, event):
        """原有文件选中事件"""
        pass

    def on_file_double_click(self, event):
        """原有双击打开文件事件"""
        pass

    def open_selected_directory(self):
        """打开选中的目录（原有功能）"""
        current_dir = self.get_current_directory()
        self.open_directory(current_dir)

    def browse_file(self):
        """浏览选择文件"""
        file_path = filedialog.askopenfilename(title="选择文件")
        if file_path:
            self.file_path_var.set(file_path)
            self.drop_text.set(f"已选择文件: {os.path.basename(file_path)}")
            self.add_log(f"已选择文件: {file_path}")

    def clear_doc_directory(self):
        """清空文档目录"""
        try:
            if not os.path.exists(DOC_FILE_DIR):
                os.makedirs(DOC_FILE_DIR)
                self.add_log(f"已创建文档目录: {DOC_FILE_DIR}")
                messagebox.showinfo("成功", "文档目录不存在，已创建")
                self.refresh_real_time_preview()
                return

            # 清空目录
            for filename in os.listdir(DOC_FILE_DIR):
                file_path = os.path.join(DOC_FILE_DIR, filename)
                try:
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.unlink(file_path)
                        self.add_log(f"已删除文件: {file_path}")
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                        self.add_log(f"已删除目录: {file_path}")
                except Exception as e:
                    self.add_log(f"删除文件失败 {file_path}: {str(e)}")

            messagebox.showinfo("成功", "文档目录已清空")
            self.add_log("文档目录已清空")
            self.refresh_real_time_preview()

        except Exception as e:
            messagebox.showerror("错误", f"清空文档目录时出错: {str(e)}")
            self.add_log(f"错误: 清空文档目录时出错: {str(e)}")

    def move_images_to_backup(self):
        """移动图片到备份目录"""
        try:
            if not os.path.exists(IMG_DIR):
                messagebox.showinfo("信息", "图片目录不存在，无需移动")
                self.add_log("图片目录不存在，无需移动")
                return

            if not os.path.exists(self.imgs_old_dir):
                os.makedirs(self.imgs_old_dir)
                self.add_log(f"已创建图片备份目录: {self.imgs_old_dir}")

            moved_count = 0
            for filename in os.listdir(IMG_DIR):
                src_path = os.path.join(IMG_DIR, filename)
                if os.path.isdir(src_path):
                    continue

                dst_path = os.path.join(self.imgs_old_dir, filename)

                # 如果目标文件已存在，添加时间戳
                if os.path.exists(dst_path):
                    base, ext = os.path.splitext(filename)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    dst_path = os.path.join(self.imgs_old_dir, f"{base}_{timestamp}{ext}")

                shutil.move(src_path, dst_path)
                self.add_log(f"已移动图片: {src_path} -> {dst_path}")
                moved_count += 1

            messagebox.showinfo("成功", f"已移动 {moved_count} 个图片文件到备份目录")
            self.add_log(f"已移动 {moved_count} 个图片文件到备份目录")
            self.refresh_real_time_preview()

        except Exception as e:
            messagebox.showerror("错误", f"移动图片到备份目录时出错: {str(e)}")
            self.add_log(f"错误: 移动图片到备份目录时出错: {str(e)}")

    def move_selected_file(self):
        """复制选中文件到文档目录（原移动功能已改为复制）"""
        try:
            file_path = self.file_path_var.get().strip()
            if not file_path:
                messagebox.showwarning("警告", "请先选择文件")
                return

            if not os.path.exists(file_path):
                messagebox.showwarning("警告", "选择的文件不存在")
                self.add_log(f"警告: 选择的文件不存在: {file_path}")
                return

            if not os.path.exists(DOC_FILE_DIR):
                os.makedirs(DOC_FILE_DIR)
                self.add_log(f"已创建文档目录: {DOC_FILE_DIR}")

            filename = os.path.basename(file_path)
            dst_path = os.path.join(DOC_FILE_DIR, filename)

            # 如果目标文件已存在，添加时间戳
            if os.path.exists(dst_path):
                base, ext = os.path.splitext(filename)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                dst_path = os.path.join(DOC_FILE_DIR, f"{base}_{timestamp}{ext}")

            # 复制文件（替换原移动操作）
            shutil.copy2(file_path, dst_path)
            self.add_log(f"已复制文件: {file_path} -> {dst_path}")
            messagebox.showinfo("成功", f"文件已复制到文档目录: {dst_path}")

            # 清空输入框
            self.file_path_var.set("")
            self.drop_text.set("请拖放文件到此处，或使用上方的浏览按钮选择文件")

            self.refresh_real_time_preview()

        except Exception as e:
            messagebox.showerror("错误", f"复制文件时出错: {str(e)}")
            self.add_log(f"错误: 复制文件时出错: {str(e)}")

    def add_log(self, message):
        """添加日志"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self.logs.append(log_entry)

        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, log_entry + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def clear_logs(self):
        """清空日志"""
        self.logs = []
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)
        self.add_log("日志已清空")


if __name__ == "__main__":
    # 安装依赖（首次运行时取消注释）
    # subprocess.run(["pip", "install", "python-docx", "Pillow", "requests"])

    root = tk.Tk()
    app = FileUploadTool(root_window=root)
    root.mainloop()