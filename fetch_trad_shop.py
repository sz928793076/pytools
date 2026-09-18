# -*- coding: utf-8 -*-
"""
trad_shop_num 数据拉取脚本
接口: https://sleye.lottery-sports.com/api/trad_shop_num
按 31 个省级行政区逐一请求，每个省保存为一个 JSON 文件
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request

# ---------------- 配置 ----------------
BASE_URL = "https://sleye.lottery-sports.com/api/trad_shop_num"
TIMESTAMP_WINDOW_BEGIN = "1755940041"   # 时间窗口起始（Unix 秒级时间戳）
SP = "ToUnderlineNoName"

# Cookie（从浏览器复制，Path=/ 等属性项会自动过滤掉）
COOKIE_RAW = (
    "Path=/; "
    "AppUser=9f17388844f5a93ccba949b7b7fc2e42eb50c7430ce3cdf20c3c7615d4ea2d6cbe374bf12d563c69661f29088f9cb8e48a598fd403ffaad2f1eda34973aceb7388d0e6ceb0ca6127f66264a65a7dea1a6c4510d1d9b0981f5c4b664c16326f7125fff58217f010b42f686809f19a389b42518ec4be13defc36a781c84c7e289bf606c102364e8ce6fad15b587262a9e69fa57e0c72abb829e05a17cc3a374f4a198bdf3bc9136e4721856b58804cd8a096034fe6e58781a291b511c7bd9da11a244cc4ca0299942556b4909e00c631bd9a90c9fd8f4c6dd9a79da6af123888eac12cd66abb622666d4044f6919cdf247585e1af3105e90d6f5fce80e62931b106dca4b4b51749a456eb10cce22f61f77; "
    "SSOUser=4e6e404c43925d0c8ca786a7873778a6; "
    "Ticket=41778736337fbabcd06bc8b142885fcaf62fbd6f55365a8d049cb1740c66b5c840ac6032437cf6559973e6a4bc330433; "
    "HeartbeatTime=249a6f7afbd45d49fe99e67253cae28445a8c0cee19990c311873cabada8e8f8; "
    "SessionID=419ae5359a0991fc07230ac79ce9cf84374f9084206cdadb5aba23d968bad2ffc765a5148ae78f57135fdb2cf5e83641"
)

# 31 个省级行政区（不含港澳台）
PROVINCES = [
    ("11", "北京"), ("12", "天津"), ("13", "河北"), ("14", "山西"), ("15", "内蒙古"),
    ("21", "辽宁"), ("22", "吉林"), ("23", "黑龙江"),
    ("31", "上海"), ("32", "江苏"), ("33", "浙江"), ("34", "安徽"), ("35", "福建"),
    ("36", "江西"), ("37", "山东"),
    ("41", "河南"), ("42", "湖北"), ("43", "湖南"), ("44", "广东"), ("45", "广西"),
    ("46", "海南"),
    ("50", "重庆"), ("51", "四川"), ("52", "贵州"), ("53", "云南"), ("54", "西藏"),
    ("61", "陕西"), ("62", "甘肃"), ("63", "青海"), ("64", "宁夏"), ("65", "新疆"),
]

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trad_shop_data")
RETRY_TIMES = 3
TIMEOUT = 30
SLEEP_BETWEEN = 1  # 每省间隔秒数，避免请求过频


def build_cookie_header(raw_cookie: str) -> str:
    """把浏览器复制的 Cookie 字符串转成请求头，过滤掉 Path 等非键值项"""
    pairs = []
    for item in raw_cookie.split(";"):
        item = item.strip()
        if not item or "=" not in item:
            continue
        key, value = item.split("=", 1)
        if key.strip().lower() == "path":
            continue
        pairs.append(f"{key.strip()}={value.strip()}")
    return "; ".join(pairs)


def fetch_province(province_code: str, cookie_header: str) -> dict:
    url = (
        f"{BASE_URL}?timestampWindowBEGIN={TIMESTAMP_WINDOW_BEGIN}"
        f"&provinceCode={province_code}&SP={SP}"
    )
    headers = {
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/126.0 Safari/537.36"),
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://sleye.lottery-sports.com/",
        "Cookie": cookie_header,
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw)


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    cookie_header = build_cookie_header(COOKIE_RAW)

    print(f"输出目录: {OUTPUT_DIR}")
    print(f"省份数量: {len(PROVINCES)}\n")

    results = []
    for code, name in PROVINCES:
        filename = f"{code}_{name}.json"
        filepath = os.path.join(OUTPUT_DIR, filename)

        ok = False
        msg = ""
        for attempt in range(1, RETRY_TIMES + 1):
            try:
                data = fetch_province(code, cookie_header)
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                ok = True
                print(f"[OK] {code} {name} -> {filename}")
                break
            except urllib.error.HTTPError as e:
                msg = f"HTTP {e.code} {e.reason}"
            except urllib.error.URLError as e:
                msg = f"网络错误 {e.reason}"
            except Exception as e:
                msg = f"{type(e).__name__}: {e}"

            print(f"[FAIL] {code} {name} 第 {attempt} 次尝试失败: {msg}")
            if attempt < RETRY_TIMES:
                time.sleep(2)

        results.append((code, name, ok, msg))
        time.sleep(SLEEP_BETWEEN)

    # 汇总
    success = [r for r in results if r[2]]
    failed = [r for r in results if not r[2]]
    print("\n========== 汇总 ==========")
    print(f"成功: {len(success)} / {len(PROVINCES)}")
    for code, name, _, _ in success:
        print(f"  [OK] {code} {name}")
    if failed:
        print("失败:")
        for code, name, _, msg in failed:
            print(f"  {code} {name}: {msg}")
        sys.exit(1)


if __name__ == "__main__":
    main()
