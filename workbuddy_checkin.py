#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WorkBuddy 每日签到（Buddy 加油站）自动领取脚本

原理
----
签到本质是一次带本机登录态的 HTTP 请求，不需要点界面：
  1. 读取本机登录态文件，取 auth.accessToken / auth.domain / auth.tokenType
  2. POST  /v2/billing/meter/checkin-activity-status   查询今日签到状态（只读）
  3. 若今日未签到，POST /v2/billing/meter/daily-checkin 领取积分

特性
----
  * 零第三方依赖（仅 Python 标准库），Python 3.7+ 即可运行
  * 幂等：已签到返回 HTTP 400 / code=10001，脚本识别为正常并跳过，不会重复领取
  * 安全：只读取登录态文件，不修改、不删除；日志与输出中 token 全程脱敏
  * 结果追加写入脚本同目录 workbuddy_checkin.log

用法
----
  python workbuddy_checkin.py            # 正常签到
  python workbuddy_checkin.py --status   # 只查状态，不签到
  python workbuddy_checkin.py --selftest # 离线自测响应判定逻辑（不联网）
  python workbuddy_checkin.py --json     # 额外输出一行 JSON 结果（便于自动化解析）
  python workbuddy_checkin.py --quiet    # 静默模式，只输出一行结论
"""

from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import urllib.error
import urllib.request
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(SCRIPT_DIR, "workbuddy_checkin.log")
DEFAULT_DOMAIN = "www.codebuddy.cn"
TIMEOUT = 20

STATUS_PATH = "/v2/billing/meter/checkin-activity-status"
CHECKIN_PATH = "/v2/billing/meter/daily-checkin"

AUTH_REL = os.path.join("CodeBuddyExtension", "Data", "Public", "auth", "workbuddy-desktop.info")


def setup_stdout():
    """Windows 控制台默认 GBK，统一改成 UTF-8，避免中文输出报错。"""
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def mask(token: str) -> str:
    if not token:
        return "(空)"
    if len(token) <= 20:
        return token[:4] + "..."
    return token[:10] + "..." + token[-4:]


# ---------------------------------------------------------------- 登录态读取

def auth_file_candidates():
    paths = []
    local = os.environ.get("LOCALAPPDATA")
    roaming = os.environ.get("APPDATA")
    if local:
        paths.append(os.path.join(local, AUTH_REL))
    if roaming:
        paths.append(os.path.join(roaming, AUTH_REL))
    home = os.path.expanduser("~")
    paths.append(os.path.join(home, "Library", "Application Support", AUTH_REL))   # macOS
    paths.append(os.path.join(home, ".config", AUTH_REL))                          # Linux
    return paths


def find_auth_file():
    for p in auth_file_candidates():
        if os.path.isfile(p):
            return p
    return None


def load_credentials():
    """返回 (token, domain, token_type, error)"""
    path = find_auth_file()
    if not path:
        return None, None, None, "未找到 WorkBuddy 登录态文件，请先打开一次 WorkBuddy 桌面端并登录"

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return None, None, None, "登录态文件解析失败: %s (%s)" % (e, path)

    auth = data.get("auth") or {}
    token = auth.get("accessToken") or ""
    if not token:
        return None, None, None, "登录态文件中没有 accessToken，请重新登录 WorkBuddy 桌面端"

    domain = (auth.get("domain") or DEFAULT_DOMAIN).strip().rstrip("/")
    if domain.startswith("http://"):
        domain = domain[7:]
    elif domain.startswith("https://"):
        domain = domain[8:]
    if not domain:
        domain = DEFAULT_DOMAIN

    token_type = auth.get("tokenType") or "Bearer"
    return token, domain, token_type, None


# ---------------------------------------------------------------- HTTP

def post_json(url: str, token: str, token_type: str):
    """返回 (status_code, response_text, error_message)"""
    req = urllib.request.Request(url, data=b"{}", method="POST")
    req.add_header("Authorization", "%s %s" % (token_type, token))
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    req.add_header("User-Agent", "WorkBuddy-Checkin/1.0")

    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx) as resp:
            return resp.status, resp.read().decode("utf-8", "replace"), None
    except urllib.error.HTTPError as e:
        try:
            text = e.read().decode("utf-8", "replace")
        except Exception:
            text = ""
        return e.code, text, None
    except Exception as e:
        return None, "", "%s: %s" % (type(e).__name__, e)


def parse_body(text: str):
    try:
        return json.loads(text)
    except Exception:
        return None


# ---------------------------------------------------------------- 响应判定

def interpret_checkin(status_code, payload, fallback_streak=None, fallback_daily=100):
    """把签到接口的响应翻译成统一结论。

    返回 dict: status / action / points / streak_days / msg

    关键点：判定只看 body 里的 code 字段。已签到时服务端返回的是
    HTTP 400 + code=10001，HTTP 状态码本身不能当作失败依据。
    """
    payload = payload or {}
    code_field = payload.get("code")
    msg_field = payload.get("msg") or payload.get("message") or ""
    data = payload.get("data") or {}

    if status_code in (401, 403):
        return {
            "status": "error",
            "action": "auth_expired",
            "points": None,
            "streak_days": fallback_streak,
            "msg": "登录态已失效（HTTP %s），请打开一次 WorkBuddy 桌面端刷新登录态后重试" % status_code,
        }

    points = data.get("credit", data.get("points", fallback_daily))
    streak = data.get("streak_days", fallback_streak)

    if code_field == 0 or (status_code == 200 and code_field is None):
        return {
            "status": "ok",
            "action": "clicked",
            "points": points,
            "streak_days": streak,
            "msg": msg_field or "签到成功，+%s 积分" % points,
        }

    if code_field == 10001 or "已签到" in msg_field:
        return {
            "status": "ok",
            "action": "skip_already_signed",
            "points": None,
            "streak_days": streak,
            "msg": msg_field or "今天已签到，请明天再来",
        }

    return {
        "status": "error",
        "action": "failed",
        "points": None,
        "streak_days": streak,
        "msg": "签到失败: HTTP %s / code=%s / %s" % (
            status_code, code_field, msg_field or str(payload)[:200]),
    }


SELFTEST_CASES = [
    ("领取成功 code=0", "ok", "clicked",
     {"code": 0, "data": {"credit": 100, "streak_days": 9}}, 200),
    ("领取成功 HTTP200 无 code", "ok", "clicked",
     {"data": {"credit": 100, "streak_days": 3}}, 200),
    ("已签到 HTTP400 code=10001", "ok", "skip_already_signed",
     {"code": 10001, "msg": "今天已签到，请明天再来"}, 400),
    ("登录态失效 401", "error", "auth_expired",
     {"code": 401, "msg": "unauthorized"}, 401),
    ("未知错误 code=50000", "error", "failed",
     {"code": 50000, "msg": "服务异常"}, 200),
    ("非 JSON 响应", "error", "failed",
     None, 502),
]


def run_selftest():
    """离线校验响应判定逻辑，不联网、不写日志、不消耗任何积分。"""
    print("WorkBuddy 签到脚本 离线自测（不联网）")
    passed = 0
    for name, exp_status, exp_action, payload, http in SELFTEST_CASES:
        got = interpret_checkin(http, payload, fallback_streak=8, fallback_daily=100)
        bad = []
        if got["status"] != exp_status:
            bad.append("status 期望 %s 实际 %s" % (exp_status, got["status"]))
        if got["action"] != exp_action:
            bad.append("action 期望 %s 实际 %s" % (exp_action, got["action"]))
        if not bad:
            passed += 1
        print("%-4s %-26s -> action=%-20s points=%s streak=%s" % (
            "PASS" if not bad else "FAIL", name, got["action"], got["points"], got["streak_days"]))
        for b in bad:
            print("     " + b)
    print("\n自测结果: %d/%d 通过" % (passed, len(SELFTEST_CASES)))
    return 0 if passed == len(SELFTEST_CASES) else 1


# ---------------------------------------------------------------- 日志

def write_log(lines):
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write("[%s] %s\n" % (stamp, " | ".join(lines)))
    except Exception:
        pass


# ---------------------------------------------------------------- 主流程

def main():
    setup_stdout()

    parser = argparse.ArgumentParser(description="WorkBuddy 每日签到（Buddy 加油站）")
    parser.add_argument("--status", action="store_true", help="只查询今日签到状态，不执行签到")
    parser.add_argument("--selftest", action="store_true", help="离线自测响应判定逻辑（不联网）")
    parser.add_argument("--json", action="store_true", help="额外输出一行 JSON 结果")
    parser.add_argument("--quiet", action="store_true", help="静默模式，只输出一行结论")
    args = parser.parse_args()

    if args.selftest:
        return run_selftest()

    now = datetime.now()
    result = {
        "time": now.strftime("%Y-%m-%d %H:%M:%S"),
        "status": "error",
        "action": "none",
        "points": None,
        "streak_days": None,
        "msg": "",
    }

    def emit(line):
        if not args.quiet:
            print(line)

    emit("WorkBuddy 每日签到  %s" % result["time"])

    token, domain, token_type, err = load_credentials()
    if err:
        result["msg"] = err
        emit("❌ " + err)
        write_log(["ERROR", err])
        if args.json:
            print(json.dumps(result, ensure_ascii=False))
        return 2

    emit("token: 已加载 %s（内容已隐藏）" % mask(token))
    emit("域名: %s" % domain)

    base = "https://%s" % domain

    # --- 1. 查询状态 ---------------------------------------------------
    code, body, herr = post_json(base + STATUS_PATH, token, token_type)
    if herr:
        result["msg"] = "查询签到状态失败: " + herr
        emit("❌ " + result["msg"])
        write_log(["ERROR", result["msg"]])
        if args.json:
            print(json.dumps(result, ensure_ascii=False))
        return 3

    payload = parse_body(body) or {}
    if code in (401, 403):
        result["msg"] = "登录态已失效（HTTP %s），请打开一次 WorkBuddy 桌面端刷新登录态后重试" % code
        emit("❌ " + result["msg"])
        write_log(["ERROR", result["msg"]])
        if args.json:
            print(json.dumps(result, ensure_ascii=False))
        return 4

    data = payload.get("data") or {}
    checked = bool(data.get("today_checked_in", False))
    streak = data.get("streak_days")
    daily = data.get("daily_credit", 100)

    if streak is not None:
        emit("连签天数: %s" % streak)

    if checked:
        result["status"] = "ok"
        result["action"] = "skip_already_signed"
        result["streak_days"] = streak
        result["msg"] = "今天已签到，无需重复领取"
        emit("✅ 今天已签到（连签 %s 天），明天再来。" % streak)
        write_log(["OK", "skip_already_signed", "streak=%s" % streak])
        if args.json:
            print(json.dumps(result, ensure_ascii=False))
        return 0

    if args.status:
        result["status"] = "ok"
        result["action"] = "query_only"
        result["msg"] = "今日尚未签到（本次仅查询，未领取）"
        emit("ℹ️ 今日尚未签到，连签 %s 天，每日可得 %s 积分（--status 未执行签到）" % (streak, daily))
        write_log(["OK", "query_only", "streak=%s" % streak])
        if args.json:
            print(json.dumps(result, ensure_ascii=False))
        return 0

    # --- 2. 执行签到 ---------------------------------------------------
    emit("今日尚未签到，正在领取…")
    code2, body2, herr2 = post_json(base + CHECKIN_PATH, token, token_type)
    if herr2:
        result["msg"] = "签到请求失败: " + herr2
        emit("❌ " + result["msg"])
        write_log(["ERROR", result["msg"]])
        if args.json:
            print(json.dumps(result, ensure_ascii=False))
        return 5

    payload2 = parse_body(body2) or {}
    verdict = interpret_checkin(code2, payload2, streak, daily)

    result["status"] = verdict["status"]
    result["action"] = verdict["action"]
    result["points"] = verdict["points"]
    result["streak_days"] = verdict["streak_days"]
    result["msg"] = verdict["msg"]

    if verdict["action"] == "clicked":
        emit("✅ 签到成功，+%s 积分，连签 %s 天。" % (verdict["points"], verdict["streak_days"]))
        write_log(["OK", "clicked", "+%s" % verdict["points"], "streak=%s" % verdict["streak_days"]])
        rc = 0
    elif verdict["action"] == "skip_already_signed":
        emit("✅ " + verdict["msg"])
        write_log(["OK", "skip_already_signed", verdict["msg"]])
        rc = 0
    elif verdict["action"] == "auth_expired":
        emit("❌ " + verdict["msg"])
        write_log(["ERROR", verdict["msg"]])
        rc = 4
    else:
        emit("❌ " + verdict["msg"])
        write_log(["ERROR", verdict["msg"]])
        rc = 5

    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    return rc


if __name__ == "__main__":
    sys.exit(main())
