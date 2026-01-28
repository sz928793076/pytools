import tkinter as tk
from tkinter import scrolledtext, filedialog, messagebox
import json
import pandas as pd


class JsonToExcelApp:
    def __init__(self, root):
        self.root = root
        self.root.title("JSON 转 Excel 工具 (企业微信数据)")
        self.root.geometry("600x500")

        # --- 1. 顶部说明 ---
        self.lbl_instruction = tk.Label(
            root,
            text="请将 JSON 数据粘贴到下方文本框，然后点击导出按钮：",
            font=("Arial", 10),
            pady=10
        )
        self.lbl_instruction.pack(side=tk.TOP, fill=tk.X, padx=10)

        # --- 2. 文本输入区域 (带滚动条) ---
        self.text_area = scrolledtext.ScrolledText(root, width=70, height=20)
        self.text_area.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)

        # --- 3. 底部按钮区域 ---
        self.btn_frame = tk.Frame(root)
        self.btn_frame.pack(pady=15)

        self.btn_clear = tk.Button(
            self.btn_frame,
            text="清空内容",
            command=self.clear_text,
            width=10
        )
        self.btn_clear.pack(side=tk.LEFT, padx=20)

        self.btn_convert = tk.Button(
            self.btn_frame,
            text="转换为 Excel 并导出",
            command=self.convert_data,
            bg="#4CAF50",
            fg="white",
            font=("Arial", 11, "bold"),
            width=20,
            height=2
        )
        self.btn_convert.pack(side=tk.LEFT, padx=20)

    def clear_text(self):
        """清空文本框"""
        self.text_area.delete("1.0", tk.END)

    def convert_data(self):
        """核心处理逻辑"""
        # 1. 获取文本框内容
        json_str = self.text_area.get("1.0", tk.END).strip()

        if not json_str:
            messagebox.showwarning("提示", "请输入 JSON 数据！")
            return

        try:
            # 2. 解析 JSON
            data = json.loads(json_str)

            # --- 智能容错处理 ---
            # 如果用户粘贴的是整个接口响应 { "errcode":0, "data": [...] }
            # 我们尝试自动定位到列表部分
            target_list = data
            if isinstance(data, dict):
                if 'data' in data and isinstance(data['data'], list):
                    target_list = data['data']
                elif 'user_list' in data and isinstance(data['user_list'], list):
                    target_list = data['user_list']
                else:
                    # 如果是字典但找不到常见列表key，尝试找字典里第一个是list的值
                    for key, val in data.items():
                        if isinstance(val, list):
                            target_list = val
                            break

            if not isinstance(target_list, list):
                messagebox.showerror("格式错误",
                                     "解析后的 JSON 不是列表格式 (List)，无法转换。\n请确认复制了正确的数据段。")
                return

            extracted_data = []

            # 3. 遍历提取字段 (你的核心逻辑)
            for item in target_list:
                if not isinstance(item, dict): continue

                # --- UserID 判断逻辑 ---
                # 优先取 wxqy_userid，如果为空或不存在，则取 acctid
                userid = item.get('wxqy_userid')
                if not userid:
                    userid = item.get('acctid', '')

                # --- 部门提取逻辑 ---
                # 优先使用 mainparty_path，如果为空则尝试使用 departy_paths 的第一个元素
                dept_path = ""

                # 安全获取 mainparty_path (防止 item.get('mainparty_path') 为 None 时报错)
                main_party = item.get('mainparty_path')
                if main_party and isinstance(main_party, dict):
                    dept_path = main_party.get('path_str', '')

                # 如果没拿到，尝试 departy_paths
                if not dept_path:
                    dep_paths = item.get('departy_paths')
                    if dep_paths and isinstance(dep_paths, list) and len(dep_paths) > 0:
                        first_path = dep_paths[0]
                        if isinstance(first_path, dict):
                            dept_path = first_path.get('path_str', '')

                # --- 组装数据 ---
                user_info = {
                    'UserID': userid,
                    '姓名': item.get('name', ''),
                    '手机号': item.get('mobile', ''),
                    '部门': dept_path
                }
                extracted_data.append(user_info)

            if not extracted_data:
                messagebox.showwarning("结果", "未提取到任何有效数据，请检查 JSON 内容。")
                return

            # 4. 弹出保存对话框
            file_path = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
                title="保存 Excel 文件"
            )

            if file_path:
                # 5. Pandas 导出
                df = pd.DataFrame(extracted_data)
                df.to_excel(file_path, index=False)
                messagebox.showinfo("成功", f"成功导出 {len(df)} 条数据！\n文件路径: {file_path}")

        except json.JSONDecodeError as e:
            messagebox.showerror("JSON 错误", f"JSON 格式解析失败，请检查复制的内容是否完整。\n错误信息: {e}")
        except Exception as e:
            messagebox.showerror("系统错误", f"发生未知错误:\n{str(e)}")


if __name__ == "__main__":
    root = tk.Tk()
    app = JsonToExcelApp(root)
    root.mainloop()