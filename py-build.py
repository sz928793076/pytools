import os
import shutil
import subprocess
import tkinter as tk
import time  # 用于日志时间格式化
from tkinter import ttk, filedialog, messagebox

# 配置：目标输出目录（替换为你的实际网络目录/本地映射路径）
TARGET_DIR = r"\\10.211.0.3\usermigration\PUB\syz\go"


class GoPackerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Go项目可视化打包工具")
        self.root.geometry("600x600")  # 整体窗口加高：从400调整为600

        # 初始化变量
        self.proj_path_var = tk.StringVar()  # Go项目路径
        self.output_name_var = tk.StringVar()  # 自定义输出文件名（初始为空）
        self.platform_var = tk.StringVar(value="local")  # 打包平台

        # 构建UI界面
        self.build_ui()

    def build_ui(self):
        # 1. 项目路径选择区域
        frame_proj = ttk.LabelFrame(self.root, text="Go项目配置", padding=10)
        frame_proj.pack(fill="x", padx=20, pady=10)

        ttk.Label(frame_proj, text="项目目录：").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(frame_proj, textvariable=self.proj_path_var, width=50).grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(frame_proj, text="浏览选择", command=self.select_proj_path).grid(row=0, column=2, padx=5, pady=5)

        ttk.Label(frame_proj, text="输出文件名：").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        output_entry = ttk.Entry(frame_proj, textvariable=self.output_name_var, width=50)
        output_entry.grid(row=1, column=1, columnspan=2, padx=5, pady=5)
        # 提示用户：默认使用项目文件夹名称，可手动修改
        output_entry.insert(0, "（选择项目后自动填充文件夹名称）")
        output_entry.configure(foreground="gray")

        # 绑定输入框焦点事件，清除提示文字
        def on_entry_focus_in(event):
            if output_entry.get() == "（选择项目后自动填充文件夹名称）":
                output_entry.delete(0, tk.END)
                output_entry.configure(foreground="black")

        def on_entry_focus_out(event):
            if not output_entry.get().strip():
                output_entry.insert(0, "（选择项目后自动填充文件夹名称）")
                output_entry.configure(foreground="gray")

        output_entry.bind("<FocusIn>", on_entry_focus_in)
        output_entry.bind("<FocusOut>", on_entry_focus_out)

        # 2. 打包平台选择区域
        frame_platform = ttk.LabelFrame(self.root, text="打包平台配置", padding=10)
        frame_platform.pack(fill="x", padx=20, pady=10)

        platform_options = [
            ("本地平台（当前系统）", "local"),
            ("Linux (amd64)", "linux_amd64"),
            ("Windows (amd64)", "win_amd64"),
            ("Mac (Intel/amd64)", "mac_amd64"),
            ("Mac (M1/M2/arm64)", "mac_arm64")
        ]

        for idx, (text, value) in enumerate(platform_options):
            ttk.Radiobutton(
                frame_platform,
                text=text,
                variable=self.platform_var,
                value=value
            ).grid(row=0, column=idx, padx=8, pady=5, sticky="w")

        # 3. 打包按钮与状态提示
        frame_operate = ttk.Frame(self.root, padding=10)
        frame_operate.pack(fill="x", padx=20, pady=10)

        self.pack_btn = ttk.Button(
            frame_operate,
            text="一键打包",
            command=self.start_pack,
            style="Accent.TButton"
        )
        self.pack_btn.pack(side="left", padx=10)

        self.status_var = tk.StringVar(value="就绪：请配置参数后点击打包")
        ttk.Label(
            frame_operate,
            textvariable=self.status_var,
            foreground="gray"
        ).pack(side="left", padx=20)

        # 4. 日志显示区域（核心修改：加高文本框）
        frame_log = ttk.LabelFrame(self.root, text="打包日志", padding=10)
        frame_log.pack(fill="both", expand=True, padx=20, pady=10)  # 占满剩余空间

        # 日志文本框高度从10调整为20，显示更多内容
        self.log_text = tk.Text(frame_log, height=20, width=70, font=("Consolas", 9))
        scrollbar = ttk.Scrollbar(frame_log, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def select_proj_path(self):
        """选择Go项目目录，并自动提取文件夹名称作为输出名"""
        path = filedialog.askdirectory(title="选择Go项目根目录")
        if path:
            self.proj_path_var.set(path)
            # 提取文件夹名称（最后一级目录名）
            proj_folder_name = os.path.basename(os.path.normpath(path))
            # 更新输出文件名输入框
            output_entry = self.root.nametowidget(".!labelframe.!entry2")  # 获取输出输入框对象
            output_entry.delete(0, tk.END)
            output_entry.configure(foreground="black")
            output_entry.insert(0, proj_folder_name)
            self.output_name_var.set(proj_folder_name)
            # 日志提示
            self.log(f"已选择项目目录：{path}")
            self.log(f"自动提取项目名称：{proj_folder_name}")

    def get_platform_config(self):
        """根据选择的平台，返回GOOS、GOARCH、文件后缀（兼容Windows/Linux/Mac）"""
        platform = self.platform_var.get()
        if platform == "local":
            # 兼容Windows/Linux/Mac的系统判断
            if os.name == "nt":  # Windows系统
                goos = "windows"
            elif os.name == "posix":
                # 判断是Linux还是Mac
                try:
                    # Mac系统的标识
                    if "darwin" in os.uname().sysname.lower():
                        goos = "darwin"
                    else:
                        goos = "linux"
                except AttributeError:
                    goos = "linux"

            # 判断架构（32/64位）
            if os.name == "nt":
                # Windows系统通过环境变量判断架构
                goarch = "amd64" if "PROGRAMFILES(X86)" in os.environ else "386"
            else:
                # Linux/Mac通过os.uname().machine判断
                goarch = "amd64" if "64" in os.uname().machine else "386"
        elif platform == "linux_amd64":
            goos, goarch = "linux", "amd64"
        elif platform == "win_amd64":
            goos, goarch = "windows", "amd64"
        elif platform == "mac_amd64":
            goos, goarch = "darwin", "amd64"
        elif platform == "mac_arm64":
            goos, goarch = "darwin", "arm64"
        else:
            goos, goarch = "linux", "amd64"

        # 文件后缀
        ext = ".exe" if goos == "windows" else ""
        return goos, goarch, ext

    def is_go_project(self, path):
        """验证是否为Go项目（存在go.mod或main.go）"""
        go_mod_path = os.path.join(path, "go.mod")
        main_go_path = os.path.join(path, "main.go")
        return os.path.exists(go_mod_path) or os.path.exists(main_go_path)

    def log(self, content):
        """日志输出到文本框（修复时间格式化问题）"""
        self.log_text.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {content}\n")
        self.log_text.see(tk.END)  # 滚动到最新日志
        self.root.update_idletasks()  # 刷新UI

    def start_pack(self):
        """开始打包流程"""
        # 禁用打包按钮，防止重复点击
        self.pack_btn.config(state="disabled")
        self.status_var.set("打包中：正在验证参数...")
        self.log("=" * 50)
        self.log("开始执行Go项目打包流程")

        try:
            # 1. 获取配置参数
            proj_path = self.proj_path_var.get().strip()
            output_name = self.output_name_var.get().strip()

            if not proj_path:
                raise Exception("请先选择Go项目目录")
            if not output_name or output_name == "（选择项目后自动填充文件夹名称）":
                # 兜底：若未自动填充，提取文件夹名称
                output_name = os.path.basename(os.path.normpath(proj_path))
                self.log(f"未自定义输出名，自动使用项目文件夹名称：{output_name}")

            # 2. 验证项目有效性
            self.log(f"验证项目目录：{proj_path}")
            if not os.path.exists(proj_path):
                raise Exception("项目目录不存在")
            if not self.is_go_project(proj_path):
                raise Exception("非Go项目（未找到go.mod或main.go文件）")
            self.log("项目验证通过")

            # 3. 获取平台配置
            goos, goarch, ext = self.get_platform_config()
            output_filename = f"{output_name}_{goos}_{goarch}{ext}"
            proj_output_path = os.path.join(proj_path, output_filename)
            target_output_path = os.path.join(TARGET_DIR, output_filename)
            self.log(f"打包平台：{goos}/{goarch}")
            self.log(f"产物名称：{output_filename}")
            self.log(f"临时输出路径：{proj_output_path}")
            self.log(f"最终目标路径：{target_output_path}")

            # 4. 执行Go编译命令
            self.status_var.set("打包中：正在编译Go项目...")
            self.log("开始编译项目（关闭CGO，移除调试信息）")
            cmd_env = os.environ.copy()
            cmd_env["GOOS"] = goos
            cmd_env["GOARCH"] = goarch
            cmd_env["CGO_ENABLED"] = "0"

            # 编译命令
            cmd = [
                "go", "build",
                "-ldflags", "-s -w",  # 减小产物体积
                "-o", output_filename
            ]

            # 执行命令并捕获输出
            result = subprocess.run(
                cmd,
                cwd=proj_path,
                env=cmd_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8"
            )

            if result.returncode != 0:
                raise Exception(f"编译失败，错误信息：\n{result.stdout}")
            self.log("项目编译成功")

            # 5. 复制产物到目标目录
            self.status_var.set("打包中：正在复制产物到目标目录...")
            self.log(f"开始复制产物到：{TARGET_DIR}")

            # 检查目标目录是否存在，不存在则创建
            if not os.path.exists(TARGET_DIR):
                os.makedirs(TARGET_DIR)
                self.log(f"目标目录不存在，已自动创建：{TARGET_DIR}")

            # 复制文件
            shutil.copy2(proj_output_path, target_output_path)
            self.log("产物复制成功")

            # 6. 清理临时产物（可选，注释则保留本地产物）
            # os.remove(proj_output_path)
            # self.log("已清理本地临时产物")

            # 打包完成
            self.status_var.set("打包成功：产物已同步到目标目录")
            self.log("=" * 50)
            self.log(f"✅ 打包完成！最终产物路径：{target_output_path}")
            messagebox.showinfo("成功", f"Go项目打包完成！\n产物路径：{target_output_path}")

        except Exception as e:
            error_msg = str(e)
            self.status_var.set("打包失败：请查看日志详情")
            self.log(f"❌ 打包失败：{error_msg}")
            messagebox.showerror("失败", f"打包出错：\n{error_msg}")

        finally:
            # 启用打包按钮
            self.pack_btn.config(state="normal")


if __name__ == "__main__":
    # 检查Go环境是否安装
    try:
        subprocess.run(
            ["go", "version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
    except FileNotFoundError:
        messagebox.critical("错误", "未检测到Go环境！请先安装Go并配置环境变量")
        exit(1)

    # 启动GUI
    root = tk.Tk()
    app = GoPackerGUI(root)
    root.mainloop()