import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import json
import requests
from datetime import datetime
import re


class LotteryDataGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("彩票数据提交工具")
        self.root.geometry("800x850")

        # 设置样式
        style = ttk.Style()
        style.configure('TLabel', font=('Arial', 10))
        style.configure('TButton', font=('Arial', 10))

        self.create_widgets()

    def create_widgets(self):
        # 创建主框架
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # URL部分
        ttk.Label(main_frame, text="接口URL:").grid(row=0, column=0, sticky=tk.W, pady=(0, 5))

        self.url_var = tk.StringVar(
            value="https://sleye-mobile.lottery.cn/crondtask/InsertData?table=paid_business_event")
        self.url_entry = ttk.Entry(main_frame, textvariable=self.url_var, width=70)
        self.url_entry.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 15))

        # Cookie输入部分
        ttk.Label(main_frame, text="Cookie:").grid(row=2, column=0, sticky=tk.W, pady=(0, 5))

        self.cookie_text = scrolledtext.ScrolledText(main_frame, height=4, width=70, font=('Arial', 10))
        self.cookie_text.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 15))

        # 文本解析输入部分
        ttk.Label(main_frame, text="文本解析 (可输入: 盗兑：15\n少兑：187\n截至2025年11月30日数据):").grid(row=4,
                                                                                                         column=0,
                                                                                                         sticky=tk.W,
                                                                                                         pady=(0, 5))

        text_parse_frame = ttk.Frame(main_frame)
        text_parse_frame.grid(row=5, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 15))

        self.parse_text = scrolledtext.ScrolledText(text_parse_frame, height=4, width=55, font=('Arial', 10))
        self.parse_text.grid(row=0, column=0, sticky=(tk.W, tk.E))

        ttk.Button(text_parse_frame, text="解析文本并生成JSON", command=self.parse_and_generate_json, width=20).grid(
            row=0, column=1, padx=(10, 0))

        # 数据输入部分
        input_frame = ttk.Frame(main_frame)
        input_frame.grid(row=6, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 15))

        # 盗兑输入
        ttk.Label(input_frame, text="盗兑:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.rob_paid_var = tk.StringVar()
        self.rob_paid_entry = ttk.Entry(input_frame, textvariable=self.rob_paid_var, width=15)
        self.rob_paid_entry.grid(row=0, column=1, sticky=tk.W, padx=(0, 30))

        # 少兑输入
        ttk.Label(input_frame, text="少兑:").grid(row=0, column=2, sticky=tk.W, padx=(0, 10))
        self.less_paid_var = tk.StringVar()
        self.less_paid_entry = ttk.Entry(input_frame, textvariable=self.less_paid_var, width=15)
        self.less_paid_entry.grid(row=0, column=3, sticky=tk.W, padx=(0, 30))

        # 截至时间输入
        ttk.Label(input_frame, text="截至时间 (示例: 2025年11月30日):").grid(row=0, column=4, sticky=tk.W, padx=(0, 10))
        self.deadline_var = tk.StringVar()
        self.deadline_entry = ttk.Entry(input_frame, textvariable=self.deadline_var, width=20)
        self.deadline_entry.grid(row=0, column=5, sticky=tk.W)

        # 按钮框架
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=7, column=0, columnspan=2, pady=(0, 15))

        ttk.Button(button_frame, text="生成JSON", command=self.generate_json).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="发送请求", command=self.send_request).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="清除数据", command=self.clear_data).pack(side=tk.LEFT)

        # JSON显示部分
        ttk.Label(main_frame, text="生成的JSON:").grid(row=8, column=0, sticky=tk.W, pady=(0, 5))

        self.json_text = scrolledtext.ScrolledText(main_frame, height=12, width=70, font=('Courier', 10))
        self.json_text.grid(row=9, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 15))

        # 响应显示部分
        ttk.Label(main_frame, text="响应结果:").grid(row=10, column=0, sticky=tk.W, pady=(0, 5))

        self.response_text = scrolledtext.ScrolledText(main_frame, height=8, width=70, font=('Arial', 10))
        self.response_text.grid(row=11, column=0, columnspan=2, sticky=(tk.W, tk.E))

        # 配置列权重
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)

    def parse_and_generate_json(self):
        """解析文本并自动生成JSON"""
        # 先解析文本
        text = self.parse_text.get(1.0, tk.END).strip()

        if not text:
            messagebox.showwarning("警告", "请输入要解析的文本")
            return

        # 初始化变量
        rob_paid = None
        less_paid = None
        deadline = None

        # 按行分割文本
        lines = text.split('\n')

        for line in lines:
            line = line.strip()

            # 匹配盗兑
            if "盗兑" in line:
                match = re.search(r'盗兑[：:]\s*(\d+)', line)
                if match:
                    rob_paid = match.group(1)

            # 匹配少兑
            if "少兑" in line:
                match = re.search(r'少兑[：:]\s*(\d+)', line)
                if match:
                    less_paid = match.group(1)

            # 匹配截至时间
            if "截至" in line:
                # 尝试多种匹配模式
                patterns = [
                    r'截至\s*(\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日)',
                    r'截至\s*(\d{4}-\d{1,2}-\d{1,2})',
                    r'截至\s*(\d{4}/\d{1,2}/\d{1,2})',
                    r'截至时间[：:]\s*(\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日)',
                    r'截至时间[：:]\s*(\d{4}-\d{1,2}-\d{1,2})',
                ]

                for pattern in patterns:
                    match = re.search(pattern, line)
                    if match:
                        deadline = match.group(1)
                        break

        # 如果没找到截至时间，尝试在整段文本中查找日期
        if not deadline:
            date_patterns = [
                r'(\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日)',
                r'(\d{4}-\d{1,2}-\d{1,2})',
                r'(\d{4}/\d{1,2}/\d{1,2})',
            ]

            for pattern in date_patterns:
                match = re.search(pattern, text)
                if match:
                    deadline = match.group(1)
                    break

        # 更新输入框
        if rob_paid:
            self.rob_paid_var.set(rob_paid)

        if less_paid:
            self.less_paid_var.set(less_paid)

        if deadline:
            # 清理日期格式
            deadline = deadline.replace(' ', '')
            self.deadline_var.set(deadline)

        # 显示解析结果
        result_message = "解析结果:\n"
        if rob_paid:
            result_message += f"盗兑: {rob_paid}\n"
        if less_paid:
            result_message += f"少兑: {less_paid}\n"
        if deadline:
            result_message += f"截至时间: {deadline}\n"

        # 自动生成JSON
        if rob_paid or less_paid or deadline:
            # 检查是否有截至时间（必须项）
            if not deadline:
                messagebox.showwarning("警告", "已解析盗兑和少兑，但未解析到截至时间，请手动输入截至时间后再生成JSON。")
                return

            # 显示解析结果提示
            messagebox.showinfo("解析成功", result_message + "\n正在自动生成JSON...")

            # 自动生成JSON
            self.generate_json()
        else:
            messagebox.showwarning("解析失败", "未能从文本中解析出有效数据")

    def parse_chinese_date(self, date_str):
        """解析中文日期格式"""
        try:
            # 清理日期字符串
            date_str = date_str.strip().replace(' ', '')

            # 匹配中文日期格式：2025年11月30日
            pattern = r'(\d{4})年(\d{1,2})月(\d{1,2})日'
            match = re.match(pattern, date_str)

            if match:
                year, month, day = match.groups()
                date_obj = datetime(int(year), int(month), int(day))
                return int(date_obj.timestamp())
            else:
                # 尝试其他格式
                date_formats = [
                    "%Y-%m-%d",
                    "%Y/%m/%d",
                    "%Y.%m.%d",
                    "%Y年%m月%d日"
                ]

                for fmt in date_formats:
                    try:
                        date_obj = datetime.strptime(date_str, fmt)
                        return int(date_obj.timestamp())
                    except ValueError:
                        continue

                raise ValueError("无法解析日期格式")
        except Exception as e:
            messagebox.showerror("错误", f"日期格式错误: {e}\n请使用格式: 2025年11月30日")
            return None

    def generate_json(self):
        """生成JSON数据"""
        try:
            # 获取输入值
            rob_paid = int(self.rob_paid_var.get().strip() or 0)
            less_paid = int(self.less_paid_var.get().strip() or 0)
            deadline = self.deadline_var.get().strip()

            if not deadline:
                messagebox.showwarning("警告", "请输入截至时间")
                return

            # 解析日期
            timestamp = self.parse_chinese_date(deadline)
            if timestamp is None:
                return

            # 计算和
            sale_event = rob_paid + less_paid

            # 构建JSON数据
            data = [{
                "abnormal_ticket_paid": 0,
                "less_paid": less_paid,
                "manage_event": 0,
                "manual_check": 0,
                "refuse_paid": 0,
                "rob_paid": rob_paid,
                "sale_event": sale_event,
                "timestamp": timestamp,
                "update_time": timestamp,
                "win_person_err": 0
            }]

            # 格式化JSON并显示
            json_str = json.dumps(data, indent=4, ensure_ascii=False)
            self.json_text.delete(1.0, tk.END)
            self.json_text.insert(1.0, json_str)

            # 清空响应框
            self.response_text.delete(1.0, tk.END)

        except ValueError as e:
            messagebox.showerror("错误", f"输入格式错误: {e}\n请确保盗兑和少兑是数字")
        except Exception as e:
            messagebox.showerror("错误", f"生成JSON时发生错误: {e}")

    def send_request(self):
        """发送POST请求"""
        try:
            # 获取JSON数据
            json_str = self.json_text.get(1.0, tk.END).strip()
            if not json_str:
                messagebox.showwarning("警告", "请先生成JSON数据")
                return

            # 获取Cookie
            cookie = self.cookie_text.get(1.0, tk.END).strip()
            if not cookie:
                messagebox.showwarning("警告", "请输入Cookie")
                return

            # 获取URL
            url = self.url_var.get().strip()
            if not url:
                messagebox.showwarning("警告", "请输入URL")
                return

            # 解析JSON数据
            data = json.loads(json_str)

            # 设置请求头
            headers = {
                'Content-Type': 'application/json',
                'Cookie': cookie
            }

            # 发送POST请求
            self.response_text.delete(1.0, tk.END)
            self.response_text.insert(1.0, "正在发送请求...\n")
            self.root.update()

            response = requests.post(url, json=data, headers=headers, timeout=30)

            # 显示响应结果
            self.response_text.delete(1.0, tk.END)
            self.response_text.insert(1.0, f"状态码: {response.status_code}\n")
            self.response_text.insert(tk.END, f"响应内容:\n")

            try:
                # 尝试解析JSON响应
                response_json = response.json()
                formatted_response = json.dumps(response_json, indent=4, ensure_ascii=False)
                self.response_text.insert(tk.END, formatted_response)
            except:
                # 如果不是JSON，显示原始文本
                self.response_text.insert(tk.END, response.text)

            # 检查请求是否成功
            if response.status_code == 200:
                self.response_text.insert(tk.END, "\n\n✅ 请求发送成功！")
            else:
                self.response_text.insert(tk.END, f"\n\n❌ 请求失败，状态码: {response.status_code}")

        except requests.exceptions.RequestException as e:
            self.response_text.delete(1.0, tk.END)
            self.response_text.insert(1.0, f"请求错误: {e}")
        except json.JSONDecodeError as e:
            self.response_text.delete(1.0, tk.END)
            self.response_text.insert(1.0, f"JSON解析错误: {e}")
        except Exception as e:
            self.response_text.delete(1.0, tk.END)
            self.response_text.insert(1.0, f"发送请求时发生错误: {e}")

    def clear_data(self):
        """清除所有数据"""
        self.rob_paid_var.set("")
        self.less_paid_var.set("")
        self.deadline_var.set("")
        self.cookie_text.delete(1.0, tk.END)
        self.parse_text.delete(1.0, tk.END)
        self.json_text.delete(1.0, tk.END)
        self.response_text.delete(1.0, tk.END)

        # 设置默认URL
        self.url_var.set("https://sleye-mobile.lottery.cn/crondtask/InsertData?table=paid_business_event")


def main():
    root = tk.Tk()
    app = LotteryDataGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()