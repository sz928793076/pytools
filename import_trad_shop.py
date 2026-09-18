# -*- coding: utf-8 -*-
"""
把 trad_shop_data 目录下 31 个省的数据通过云上 InsertData 接口批量导入
实现参考 importCloud.py：
    POST https://sf-sleye.lottery-sports.com/crondtask/InsertData?table=<table>
    body = JSON 数组，Content-Type: application/json，Cookie 走请求头

用法:
    python import_trad_shop.py                              # 全量导入（默认表名 trad_shop_num）
    python import_trad_shop.py --table xxx                  # 指定云上表名
    python import_trad_shop.py --limit 5                    # 冒烟测试，只导前 5 条
    python import_trad_shop.py --batch 200                  # 调整批次大小
    python import_trad_shop.py --log import.log             # 日志实时写入文件（逐行 flush）
"""

import argparse
import json
import os
import sys
import time

import requests

# ---------------- 配置 ----------------
INSERT_URL = "https://sf-sleye.lottery-sports.com/crondtask/InsertData"
DEFAULT_TABLE = "trad_shop_num"
BATCH_SIZE = 500
MAX_RETRIES = 3
TIMEOUT = 60
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trad_shop_data")

# Cookie（浏览器复制，Path=/ 等属性项自动过滤）
COOKIE_RAW = (
    "Path=/; "
    "AppUser=989865ffb63033811407e9b9922c912120b4e5dde8f1f6a7b8ea895417460b96ddebb3a3b81ae5b62623e0205cec8a725c083967011b664cad1ba5c8de29b0c85986e371b6ee13acbf08614ecbc46bc16ffa11a498c468996d4e333d39049484d5ef08d03aae81b706394283e1f8469ab008c232aa2479ed536785edabbf684721137439962873124c72dfe911ac5c7fa7c7db9ced88fcb5e2906dcd616f90d724aaae341220b6a033150c8cd1f619065fa57c9d49893fa7cb7d25e3a5ac84c0dc3946fd6c747ae5e3795eb854cd7fc3d1d70c8afec446d94857fac74408ec10636b97c77f1c8ee936d11a6e1557ae147d412833642533e0167a5ea1341da31b6e1e3295fb55f56c78e96c23e056f85b; "
    "SSOUser=00cae31008b0da02d78b0eb4872df1e1; "
    "Ticket=d8ff5a88bbf8d51b62faf39954bbe5cbe501d706040a4383c045e9bb6a7793b87fadcb6aa6e3c6356ecc34c859a5a442809d336730d6492d19379d5955e8418f; "
    "HeartbeatTime=2e53c7e581edd02ea1a72516a6498ce1164c2e25ddc2aeb8f576602d6a077bcb; "
    "SessionID=b3b78a95d1b5135f2456e79a32acb4e17d0cb68ac62ef3d641295880382adb516432ee902625da0fa2cbb3332ac49269"
)

# 日志文件句柄（--log 指定后启用）
LOG_FH = None


def log(msg: str = "", end: str = "\n"):
    """实时输出日志：stdout 强制 flush；若指定了 --log 文件，同步逐行写入并 flush"""
    print(msg, end=end, flush=True)
    if LOG_FH is not None:
        LOG_FH.write(msg + end)
        LOG_FH.flush()


def build_cookie_header(raw_cookie: str) -> str:
    """把浏览器复制的 Cookie 字符串转成请求头，过滤 Path 等非键值项"""
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


def load_all_data(data_dir: str) -> list:
    """读取目录下所有 json 文件，合并为 list"""
    all_data = []
    files = sorted(f for f in os.listdir(data_dir) if f.endswith(".json"))
    if not files:
        raise SystemExit(f"目录 {data_dir} 下没有 json 文件")
    for f in files:
        path = os.path.join(data_dir, f)
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, list):
            log(f"⚠️ 跳过 {f}: 顶层不是数组")
            continue
        all_data.extend(data)
        log(f"加载 {f}: {len(data)} 条")
    return all_data


def validate_and_filter(data_array: list) -> list:
    """过滤不可序列化的数据"""
    valid = []
    invalid = 0
    for item in data_array:
        try:
            json.dumps(item, ensure_ascii=False)
            valid.append(item)
        except Exception:
            invalid += 1
    if invalid:
        log(f"⚠️ 跳过 {invalid} 条不可序列化数据")
    return valid


def send_batch(batch: list, table: str, cookie: str, batch_idx: int, total: int):
    """发送一个批次，返回 (是否成功, 服务端确认插入数)"""
    url = f"{INSERT_URL}?table={table}"
    headers = {"Content-Type": "application/json", "Cookie": cookie}
    body = json.dumps(batch, ensure_ascii=False)
    expected = len(batch)
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(url, data=body, headers=headers, timeout=TIMEOUT)
            resp.raise_for_status()
            inserted = expected
            try:
                rj = resp.json()
                if isinstance(rj, dict):
                    if "inserted" in rj:
                        inserted = int(rj["inserted"])
                    elif isinstance(rj.get("data"), dict) and "inserted" in rj["data"]:
                        inserted = int(rj["data"]["inserted"])
                    elif "inserted_count" in rj:
                        inserted = int(rj["inserted_count"])
            except Exception:
                pass
            if inserted != expected:
                log(f"⚠️ 批次 {batch_idx}/{total}: 服务端插入 {inserted} 条，本地 {expected} 条")
            return True, inserted
        except requests.exceptions.RequestException as e:
            if attempt < MAX_RETRIES:
                log(f"批次 {batch_idx}/{total} 第 {attempt} 次失败: {e}，{2 ** attempt}s 后重试...")
                time.sleep(2 ** attempt)
            else:
                log(f"❌ 批次 {batch_idx}/{total} 最终失败: {e}")
                return False, 0
    return False, 0


def main():
    parser = argparse.ArgumentParser(description="导入 trad_shop_num 数据到云上库")
    parser.add_argument("--table", default=DEFAULT_TABLE, help=f"云上表名（默认 {DEFAULT_TABLE}）")
    parser.add_argument("--batch", type=int, default=BATCH_SIZE, help=f"批次大小（默认 {BATCH_SIZE}）")
    parser.add_argument("--limit", type=int, default=0, help="只导入前 N 条（冒烟测试用，0=全部）")
    parser.add_argument("--data-dir", default=DATA_DIR, help=f"数据目录（默认 {DATA_DIR}）")
    parser.add_argument("--log", default="", help="日志文件路径，日志将实时逐行写入该文件")
    args = parser.parse_args()

    global LOG_FH
    if args.log:
        LOG_FH = open(args.log, "w", encoding="utf-8")
        log(f"日志文件: {args.log}（实时写入）")

    cookie = build_cookie_header(COOKIE_RAW)
    all_data = load_all_data(args.data_dir)
    valid_data = validate_and_filter(all_data)
    if args.limit > 0:
        valid_data = valid_data[:args.limit]
        log(f"测试模式: 仅导入前 {len(valid_data)} 条")

    if not valid_data:
        raise SystemExit("没有有效数据")

    batches = [valid_data[i:i + args.batch] for i in range(0, len(valid_data), args.batch)]
    total_batches = len(batches)
    total_expected = len(valid_data)
    total_inserted = 0
    failed_batches = []
    start = time.time()

    log(f"\n共 {total_expected} 条，拆分为 {total_batches} 个批次，表名: {args.table}")
    log("开始导入...\n")

    for idx, batch in enumerate(batches, 1):
        ok, inserted = send_batch(batch, args.table, cookie, idx, total_batches)
        total_inserted += inserted
        if not ok:
            failed_batches.append(idx)
        if idx % 10 == 0 or idx == 1 or idx == total_batches:
            elapsed = time.time() - start
            avg = elapsed / idx
            remain = avg * (total_batches - idx)
            log(f"[{idx}/{total_batches}] 已插入 {total_inserted}/{total_expected} 条，"
                f"用时 {elapsed:.0f}s，预计剩余 {remain:.0f}s")

    elapsed = time.time() - start
    log("\n========== 最终统计 ==========")
    log(f"总耗时: {elapsed:.2f} 秒")
    log(f"应插入: {total_expected} 条")
    log(f"实际插入: {total_inserted} 条")
    log(f"丢失: {total_expected - total_inserted} 条")
    log(f"失败批次: {failed_batches if failed_batches else '无'}")

    if LOG_FH is not None:
        LOG_FH.close()
    sys.exit(1 if failed_batches else 0)


if __name__ == "__main__":
    main()
