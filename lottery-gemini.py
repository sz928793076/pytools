import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import random
from collections import Counter


class LotteryEngine:
    def __init__(self):
        self.mode = "dlt"  # 默认大乐透
        self.history_data = ""
        self.stats = Counter()  # 全局统计 (用于数字型)
        self.front_stats = Counter()  # 前区统计 (用于乐透型)
        self.back_stats = Counter()  # 后区统计 (用于乐透型)

    def set_mode(self, mode):
        self.mode = mode
        # 切换模式后重新分析数据
        self.analyze_data()

    def analyze_data(self):
        """根据当前模式解析数据"""
        self.stats.clear()
        self.front_stats.clear()
        self.back_stats.clear()

        lines = self.history_data.strip().split('\n')
        for line in lines:
            # 预处理：去除多余符号，只留数字和空格/加号
            clean_line = line.replace('+', ' ').replace(',', ' ')
            parts = clean_line.split()

            # 过滤掉显然不是号码的部分 (如期号 26009)
            # 简单假设：大号码(>35)或长数字串通常是期号，我们只取前N个
            nums = []
            for p in parts:
                if p.isdigit() and len(p) <= 2:  # 假设单个数不超过2位
                    nums.append(int(p))

            if not nums: continue

            if self.mode == "dlt":
                # 大乐透逻辑: 前5 + 后2
                if len(nums) >= 7:
                    self.front_stats.update(nums[:5])
                    self.back_stats.update(nums[5:7])

            elif self.mode == "pl5":
                # 排列5逻辑: 5个数字 (0-9)
                # 统计所有出现的数字频率
                if len(nums) >= 5:
                    self.stats.update(nums[:5])

            elif self.mode == "qxc":
                # 七星彩逻辑: 前6 (0-9) + 后1 (0-14)
                if len(nums) >= 7:
                    # 为了简单，前6位算前区，最后1位单独统计
                    self.front_stats.update(nums[:6])
                    self.back_stats.update([nums[6]])

    def get_weighted_sample(self, pool, stats, k, allow_repeat=False, inverse=False):
        """通用的加权随机生成器"""
        weights = []
        for num in pool:
            count = stats[num]
            # 平滑处理：如果没有数据，给一个基础权重 1
            if count == 0: count = 1

            if inverse:
                weight = 1000 / count  # 冷号权重高
            else:
                weight = count  # 热号权重高
            weights.append(weight)

        if allow_repeat:
            # 排列5/七星彩：允许重复 (使用 choices)
            return random.choices(pool, weights=weights, k=k)
        else:
            # 大乐透：不允许重复 (使用无放回抽样，需手写循环)
            result = set()
            # 简单的加权无放回逻辑
            temp_pool = list(pool)
            temp_weights = list(weights)

            while len(result) < k and temp_pool:
                pick = random.choices(temp_pool, weights=temp_weights, k=1)[0]
                if pick not in result:
                    result.add(pick)
            return sorted(list(result))

    def generate(self, strategy, count=5):
        results = []

        for _ in range(count):
            line_str = ""

            # === 1. 大乐透 (Lotto) ===
            if self.mode == "dlt":
                front_pool = list(range(1, 36))
                back_pool = list(range(1, 13))

                # 前区逻辑
                if strategy == "hot":
                    f_nums = self.get_weighted_sample(front_pool, self.front_stats, 5, False, False)
                elif strategy == "cold":
                    f_nums = self.get_weighted_sample(front_pool, self.front_stats, 5, False, True)
                elif strategy == "balance":  # 奇偶平衡
                    odds = [n for n in front_pool if n % 2 != 0]
                    evens = [n for n in front_pool if n % 2 == 0]
                    f_nums = sorted(random.sample(odds, 3) + random.sample(evens, 2))
                else:  # 连号/大跨度/随机 暂统一用随机，保留接口
                    f_nums = sorted(random.sample(front_pool, 5))

                # 后区逻辑 (简单加权)
                b_nums = self.get_weighted_sample(back_pool, self.back_stats, 2, False, False)

                line_str = f"前[{' '.join(f'{n:02d}' for n in f_nums)}] + 后[{' '.join(f'{n:02d}' for n in b_nums)}]"

            # === 2. 排列5 (Digital 5) ===
            elif self.mode == "pl5":
                pool = list(range(0, 10))

                if strategy == "hot":
                    # 基于数字出现的总频次加权
                    nums = self.get_weighted_sample(pool, self.stats, 5, True, False)
                elif strategy == "cold":
                    nums = self.get_weighted_sample(pool, self.stats, 5, True, True)
                elif strategy == "consecutive":
                    # 排列5的“连号”通常指出现了 1 2 3 这种顺子，或者 AABBC
                    # 这里生成一组包含顺子的号码
                    start = random.randint(0, 5)
                    nums = [start, start + 1, start + 2, random.randint(0, 9), random.randint(0, 9)]
                    random.shuffle(nums)
                elif strategy == "balance":
                    # 3奇2偶
                    odds = [1, 3, 5, 7, 9]
                    evens = [0, 2, 4, 6, 8]
                    nums = random.choices(odds, k=3) + random.choices(evens, k=2)
                    random.shuffle(nums)
                else:
                    nums = [random.randint(0, 9) for _ in range(5)]

                line_str = " ".join(str(n) for n in nums)

            # === 3. 七星彩 (Digital 6+1) ===
            elif self.mode == "qxc":
                f_pool = list(range(0, 10))
                b_pool = list(range(0, 15))  # 第7位是0-14

                # 前6位
                if strategy == "hot":
                    f_nums = self.get_weighted_sample(f_pool, self.front_stats, 6, True, False)
                elif strategy == "cold":
                    f_nums = self.get_weighted_sample(f_pool, self.front_stats, 6, True, True)
                else:
                    f_nums = [random.randint(0, 9) for _ in range(6)]

                # 第7位
                b_num = self.get_weighted_sample(b_pool, self.back_stats, 1, True, False)[0]

                line_str = f"{' '.join(str(n) for n in f_nums)} + {b_num}"

            results.append(line_str)

        return results


# --- GUI 界面类 ---
class LotteryApp:
    def __init__(self, root):
        self.root = root
        self.root.title("全能彩票分析师 V2.0 (大乐透/排列5/七星彩)")
        self.root.geometry("650x750")

        self.engine = LotteryEngine()
        self.create_widgets()

    def create_widgets(self):
        # 1. 顶部控制栏
        frame_top = tk.Frame(self.root, bg="#f0f0f0", pady=10)
        frame_top.pack(fill=tk.X)

        tk.Label(frame_top, text="选择彩种:", font=("Arial", 12, "bold"), bg="#f0f0f0").pack(side=tk.LEFT, padx=10)

        self.mode_var = tk.StringVar(value="dlt")
        modes = [("大乐透 (5+2)", "dlt"), ("排列5 (5位)", "pl5"), ("七星彩 (6+1)", "qxc")]

        for text, val in modes:
            tk.Radiobutton(frame_top, text=text, variable=self.mode_var, value=val,
                           command=self.on_mode_change, bg="#f0f0f0", font=("Arial", 10)).pack(side=tk.LEFT, padx=5)

        # 2. 历史数据区域
        tk.Label(self.root, text="历史数据 (直接粘贴，不同游戏请先清空):", font=("Arial", 10)).pack(pady=5)
        self.text_data = scrolledtext.ScrolledText(self.root, height=10, width=70)
        self.text_data.pack(padx=10)

        # 默认给一点提示
        self.text_data.insert(tk.END,
                              "请在此处粘贴历史数据...\n大乐透示例: 05 12 13... + 05 08\n排列5示例: 1 5 2 9 3 26001\n七星彩示例: 1 2 3 4 5 6 14")

        btn_update = tk.Button(self.root, text="📥 载入/分析数据", command=self.update_stats, bg="#dddddd", width=20)
        btn_update.pack(pady=5)

        # 3. 策略生成区域
        tk.Label(self.root, text="--- 选择生成策略 ---", fg="gray").pack(pady=10)

        frame_btns = tk.Frame(self.root)
        frame_btns.pack()

        # 策略按钮组
        strategies = [
            ("🔥 热号 (高频)", "hot", "#ffcccc"),
            ("🧊 冷号 (遗漏)", "cold", "#ccefff"),
            ("🔗 连号/顺子", "consecutive", "#e6ffcc"),
            ("⚖️ 奇偶平衡", "balance", "#ffffcc"),
            ("🎲 纯随机", "random", "#f2ccff")
        ]

        for text, mode, color in strategies:
            tk.Button(frame_btns, text=text, bg=color, width=12, height=2,
                      command=lambda m=mode: self.run_generation(m)).pack(side=tk.LEFT, padx=3)

        # 注数输入
        frame_count = tk.Frame(self.root)
        frame_count.pack(pady=5)
        tk.Label(frame_count, text="生成注数:").pack(side=tk.LEFT)
        self.entry_count = tk.Entry(frame_count, width=5)
        self.entry_count.insert(0, "5")
        self.entry_count.pack(side=tk.LEFT)

        # 4. 结果显示
        tk.Label(self.root, text="推荐号码:", font=("Arial", 12, "bold")).pack(pady=5)
        self.text_result = scrolledtext.ScrolledText(self.root, height=10, width=60, font=("Courier New", 14))
        self.text_result.pack(padx=10, pady=5)

    def on_mode_change(self):
        mode = self.mode_var.get()
        self.engine.set_mode(mode)
        self.text_result.delete("1.0", tk.END)
        self.text_result.insert(tk.END, f"已切换到模式: {mode.upper()}\n请粘贴对应历史数据并点击'载入数据'。")

    def update_stats(self):
        data = self.text_data.get("1.0", tk.END)
        self.engine.history_data = data
        self.engine.analyze_data()
        mode_name = {"dlt": "大乐透", "pl5": "排列5", "qxc": "七星彩"}.get(self.engine.mode)
        messagebox.showinfo("成功", f"{mode_name} 数据分析完成！\n现在可以使用策略按钮生成号码了。")

    def run_generation(self, strategy):
        try:
            count = int(self.entry_count.get())
        except:
            count = 5

        results = self.engine.generate(strategy, count)

        self.text_result.delete("1.0", tk.END)
        self.text_result.insert(tk.END, f"=== {self.engine.mode.upper()} : {strategy} ===\n\n")
        for line in results:
            self.text_result.insert(tk.END, line + "\n")


if __name__ == "__main__":
    root = tk.Tk()
    app = LotteryApp(root)
    root.mainloop()