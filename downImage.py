import os
import re
import requests
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ---------- 配置 ----------
# 原始 Cookie 字符串（完整）
COOKIE_STR = (
    "Path=/; Path=/; AppUser=9f17388844f5a93ccba949b7b7fc2e42eb50c7430ce3cdf20c3c7615d4ea2d6cbe374bf12d563c69661f29088f9cb8e48a598fd403ffaad2f1eda34973aceb7388d0e6ceb0ca6127f66264a65a7dea1a6c4510d1d9b0981f5c4b664c16326f7125fff58217f010b42f686809f19a389b42518ec4be13defc36a781c84c7e289bf606c102364e8ce6fad15b587262a9e69fa57e0c72abb829e05a17cc3a374f4a198bdf3bc9136e4721856b58804cd8a096034fe6e58781a291b511c7bd9da11a244cc4ca0299942556b4909e00c631bd9a90c9fd8f4c6dd9a79da6af123888eac12cd66abb622666d4044f6919cdf247585e1af3105e90d6f5fce80e62931b106dca4b4b51749a456eb10cce22f61f77; "
    "SSOUser=4e6e404c43925d0c8ca786a7873778a6; Ticket=183d2c2584802a6d66b570b3b1a032805fee0917bba006e598481a2c24f278c7029d407677b043c9c7db06b3facd9da8b7fc2a7454f57960ccb9f594f5d3e910; "
    "HeartbeatTime=fd9e4597fc1fea3f6f8b4be574825932981a91697e74c2ccc3ba268a392272ad; SessionID=ecba890431dabe96d4b22e8fea859ae164647fd6a17d8975b4e98d1fff474a39b3b02e58e4d75595d1d44673690d3aae"
)

# 请求头（从 curl 中提取）
HEADERS = {
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
    'Connection': 'keep-alive',
    'Origin': 'https://sleye-mobile.lottery.cn',
    'Referer': 'https://sleye-mobile.lottery.cn/ubmscreen-jk-new/jk-new',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36 Edg/145.0.0.0',
    'sec-ch-ua': '"Not:A-Brand";v="99", "Microsoft Edge";v="145", "Chromium";v="145"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-origin',
    'Cookie': COOKIE_STR,  # 直接发送原始字符串
}

# 下载目录
DOWNLOAD_DIR = "downloaded_images"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ---------- 参数列表（请将您的完整列表粘贴在此处）----------
params_list = [
  {
    "faceAmount": 5,
    "gameName": "666"
  },
  {
    "faceAmount": 30,
    "gameName": "95至尊"
  },
  {
    "faceAmount": 10,
    "gameName": "为中国力量加油"
  },
  {
    "faceAmount": 10,
    "gameName": "合体字"
  },
  {
    "faceAmount": 10,
    "gameName": "四美"
  },
  {
    "faceAmount": 20,
    "gameName": "大运到"
  },
  {
    "faceAmount": 10,
    "gameName": "大运连连"
  },
  {
    "faceAmount": 5,
    "gameName": "妙"
  },
  {
    "faceAmount": 10,
    "gameName": "火星计划"
  },
  {
    "faceAmount": 5,
    "gameName": "牛"
  },
  {
    "faceAmount": 20,
    "gameName": "牛气冲天"
  },
  {
    "faceAmount": 10,
    "gameName": "相约亚沙"
  },
  {
    "faceAmount": 10,
    "gameName": "翻倍赢家"
  },
  {
    "faceAmount": 20,
    "gameName": "翻倍赢家"
  },
  {
    "faceAmount": 5,
    "gameName": "翻倍赢家"
  },
  {
    "faceAmount": 10,
    "gameName": "进球啦"
  },
  {
    "faceAmount": 10,
    "gameName": "金牛贺岁"
  },
  {
    "faceAmount": 10,
    "gameName": "进球啦"
  },
  {
    "faceAmount": 30,
    "gameName": "95至尊"
  },
  {
    "faceAmount": 5,
    "gameName": "666"
  },
  {
    "faceAmount": 30,
    "gameName": "95至尊"
  },
  {
    "faceAmount": 20,
    "gameName": "大运到"
  },
  {
    "faceAmount": 10,
    "gameName": "大运连连"
  },
  {
    "faceAmount": 10,
    "gameName": "火星计划"
  },
  {
    "faceAmount": 5,
    "gameName": "牛"
  },
  {
    "faceAmount": 20,
    "gameName": "牛气冲天"
  },
  {
    "faceAmount": 10,
    "gameName": "相约亚沙"
  },
  {
    "faceAmount": 10,
    "gameName": "金牛贺岁"
  },
  {
    "faceAmount": 20,
    "gameName": "大运到"
  },
  {
    "faceAmount": 5,
    "gameName": "666"
  },
  {
    "faceAmount": 30,
    "gameName": "95至尊"
  },
  {
    "faceAmount": 20,
    "gameName": "大运到"
  },
  {
    "faceAmount": 10,
    "gameName": "大运连连"
  },
  {
    "faceAmount": 10,
    "gameName": "火星计划"
  },
  {
    "faceAmount": 5,
    "gameName": "牛"
  },
  {
    "faceAmount": 20,
    "gameName": "牛气冲天"
  },
  {
    "faceAmount": 10,
    "gameName": "相约亚沙"
  },
  {
    "faceAmount": 10,
    "gameName": "金牛贺岁"
  },
  {
    "faceAmount": 10,
    "gameName": "进球啦"
  },
  {
    "faceAmount": 10,
    "gameName": "为中国力量加油"
  },
  {
    "faceAmount": 10,
    "gameName": "为中国力量加油 全运会"
  },
  {
    "faceAmount": 20,
    "gameName": "五虎将"
  },
  {
    "faceAmount": 20,
    "gameName": "翻倍赢家"
  },
  {
    "faceAmount": 20,
    "gameName": "五虎将"
  },
  {
    "faceAmount": 10,
    "gameName": "翻倍赢家"
  },
  {
    "faceAmount": 30,
    "gameName": "95至尊"
  },
  {
    "faceAmount": 10,
    "gameName": "进球啦"
  },
  {
    "faceAmount": 10,
    "gameName": "好运沈阳"
  },
  {
    "faceAmount": 10,
    "gameName": "好彩头"
  },
  {
    "faceAmount": 20,
    "gameName": "五虎将"
  },
  {
    "faceAmount": 20,
    "gameName": "翻倍赢家"
  },
  {
    "faceAmount": 10,
    "gameName": "翻倍赢家"
  },
  {
    "faceAmount": 30,
    "gameName": "95至尊"
  },
  {
    "faceAmount": 10,
    "gameName": "进球啦"
  },
  {
    "faceAmount": 10,
    "gameName": "好运沈阳"
  },
  {
    "faceAmount": 10,
    "gameName": "好彩头"
  },
  {
    "faceAmount": 5,
    "gameName": "翻倍赢家"
  },
  {
    "faceAmount": 10,
    "gameName": "火星计划"
  },
  {
    "faceAmount": 10,
    "gameName": "为中国力量加油 全运会"
  },
  {
    "faceAmount": 20,
    "gameName": "好彩头"
  },
  {
    "faceAmount": 10,
    "gameName": "红都瑞金"
  },
  {
    "faceAmount": 50,
    "gameName": "8"
  },
  {
    "faceAmount": 5,
    "gameName": "爱赢"
  },
  {
    "faceAmount": 5,
    "gameName": "宝石之王"
  },
  {
    "faceAmount": 20,
    "gameName": "红红火火"
  },
  {
    "faceAmount": 10,
    "gameName": "虎丘风光"
  },
  {
    "faceAmount": 20,
    "gameName": "虎丘风光"
  },
  {
    "faceAmount": 5,
    "gameName": "全民健身 我来啦"
  },
  {
    "faceAmount": 10,
    "gameName": "全民健身 我来啦"
  },
  {
    "faceAmount": 30,
    "gameName": "万里长城"
  },
  {
    "faceAmount": 20,
    "gameName": "中国腾冲"
  },
  {
    "faceAmount": 10,
    "gameName": "说走就走"
  },
  {
    "faceAmount": 50,
    "gameName": "8"
  },
  {
    "faceAmount": 50,
    "gameName": "8"
  },
  {
    "faceAmount": 10,
    "gameName": "8"
  },
  {
    "faceAmount": 20,
    "gameName": "8"
  },
  {
    "faceAmount": 10,
    "gameName": "任意球大师"
  },
  {
    "faceAmount": 5,
    "gameName": "保持微笑"
  },
  {
    "faceAmount": 10,
    "gameName": "我爱中国II"
  },
  {
    "faceAmount": 10,
    "gameName": "翻倍好运"
  },
  {
    "faceAmount": 20,
    "gameName": "翻倍好运"
  },
  {
    "faceAmount": 5,
    "gameName": "翻倍好运"
  },
  {
    "faceAmount": 10,
    "gameName": "我爱中国Ⅱ"
  },
  {
    "faceAmount": 5,
    "gameName": "卯兔"
  },
  {
    "faceAmount": 50,
    "gameName": "新春大吉"
  },
  {
    "faceAmount": 10,
    "gameName": "玉兔贺岁"
  },
  {
    "faceAmount": 20,
    "gameName": "瑞兔呈祥"
  },
  {
    "faceAmount": 10,
    "gameName": "爱冰雪一起赢"
  },
  {
    "faceAmount": 10,
    "gameName": "爱冰雪一起赢"
  },
  {
    "faceAmount": 10,
    "gameName": "红包来啦让好事发生"
  },
  {
    "faceAmount": 10,
    "gameName": "红包来啦让好事发生"
  },
  {
    "faceAmount": 10,
    "gameName": "红包来啦 让好事发生"
  },
  {
    "faceAmount": 10,
    "gameName": "爱冰雪 一起赢"
  },
  {
    "faceAmount": 10,
    "gameName": "爱冰雪 一起赢"
  },
  {
    "faceAmount": 10,
    "gameName": "红包来啦 让好事发生"
  },
  {
    "faceAmount": 10,
    "gameName": "体育科普 即刻出彩"
  },
  {
    "faceAmount": 30,
    "gameName": "火凤凰"
  },
  {
    "faceAmount": 10,
    "gameName": "超级加倍Ⅱ"
  },
  {
    "faceAmount": 20,
    "gameName": "超级加倍Ⅱ"
  },
  {
    "faceAmount": 5,
    "gameName": "超级加倍Ⅱ"
  },
  {
    "faceAmount": 50,
    "gameName": "超级加倍Ⅱ"
  },
  {
    "faceAmount": 20,
    "gameName": "为中国力量加油 亚运会"
  },
  {
    "faceAmount": 2,
    "gameName": "有礼了"
  },
  {
    "faceAmount": 10,
    "gameName": "为中国力量加油 铿锵玫瑰"
  },
  {
    "faceAmount": 10,
    "gameName": "亮丽内蒙古"
  },
  {
    "faceAmount": 20,
    "gameName": "亮丽内蒙古"
  },
  {
    "faceAmount": 10,
    "gameName": "全民健身 我来啦II"
  },
  {
    "faceAmount": 5,
    "gameName": "全民健身 我来啦II"
  },
  {
    "faceAmount": 10,
    "gameName": "接好运"
  },
  {
    "faceAmount": 20,
    "gameName": "接好运"
  },
  {
    "faceAmount": 50,
    "gameName": "接好运"
  },
  {
    "faceAmount": 10,
    "gameName": "美丽中国 青海画卷"
  },
  {
    "faceAmount": 20,
    "gameName": "美丽中国 青海画卷"
  },
  {
    "faceAmount": 10,
    "gameName": "说走就走II"
  },
  {
    "faceAmount": 10,
    "gameName": "为中国力量加油 铿锵玫瑰"
  },
  {
    "faceAmount": 10,
    "gameName": "亮丽内蒙古"
  },
  {
    "faceAmount": 20,
    "gameName": "亮丽内蒙古"
  },
  {
    "faceAmount": 10,
    "gameName": "全民健身 我来啦II"
  },
  {
    "faceAmount": 5,
    "gameName": "全民健身 我来啦II"
  },
  {
    "faceAmount": 10,
    "gameName": "我爱中国2023"
  },
  {
    "faceAmount": 10,
    "gameName": "接好运"
  },
  {
    "faceAmount": 20,
    "gameName": "接好运"
  },
  {
    "faceAmount": 50,
    "gameName": "接好运"
  },
  {
    "faceAmount": 10,
    "gameName": "美丽中国 青海画卷"
  },
  {
    "faceAmount": 20,
    "gameName": "美丽中国 青海画卷"
  },
  {
    "faceAmount": 10,
    "gameName": "说走就走II"
  },
  {
    "faceAmount": 20,
    "gameName": "锦鲤大王"
  },
  {
    "faceAmount": 20,
    "gameName": "国宝III"
  },
  {
    "faceAmount": 10,
    "gameName": "我爱篮球II"
  },
  {
    "faceAmount": 20,
    "gameName": "国宝Ⅲ"
  },
  {
    "faceAmount": 10,
    "gameName": "我爱篮球Ⅱ"
  },
  {
    "faceAmount": 10,
    "gameName": "共富浙江 赛事助力篇"
  },
  {
    "faceAmount": 20,
    "gameName": "有一种叫云南的生活"
  },
  {
    "faceAmount": 10,
    "gameName": "桂林山水 甲天下"
  },
  {
    "faceAmount": 10,
    "gameName": "上冰雪 尽情嗨"
  },
  {
    "faceAmount": 10,
    "gameName": "射门得奖"
  },
  {
    "faceAmount": 10,
    "gameName": "酷酷的海南"
  },
  {
    "faceAmount": 30,
    "gameName": "抢头彩2024"
  },
  {
    "faceAmount": 50,
    "gameName": "新春大吉2024"
  },
  {
    "faceAmount": 10,
    "gameName": "祥龙贺岁"
  },
  {
    "faceAmount": 5,
    "gameName": "辰龙"
  },
  {
    "faceAmount": 20,
    "gameName": "龙行大运"
  },
  {
    "faceAmount": 10,
    "gameName": "彩运来"
  },
  {
    "faceAmount": 30,
    "gameName": "锦绣国韵"
  },
  {
    "faceAmount": 30,
    "gameName": "体彩发行30周年"
  },
  {
    "faceAmount": 10,
    "gameName": "超级加倍Ⅲ"
  },
  {
    "faceAmount": 20,
    "gameName": "超级加倍Ⅲ"
  },
  {
    "faceAmount": 50,
    "gameName": "超级加倍Ⅲ"
  },
  {
    "faceAmount": 10,
    "gameName": "红包来啦 让好事发生2024"
  },
  {
    "faceAmount": 20,
    "gameName": "为中国力量加油2024"
  },
  {
    "faceAmount": 20,
    "gameName": "为中国力量加油2024"
  },
  {
    "faceAmount": 10,
    "gameName": "倍儿爽"
  },
  {
    "faceAmount": 10,
    "gameName": "出7制胜"
  },
  {
    "faceAmount": 20,
    "gameName": "国宝"
  },
  {
    "faceAmount": 10,
    "gameName": "棋王"
  },
  {
    "faceAmount": 20,
    "gameName": "锦鲤"
  },
  {
    "faceAmount": 20,
    "gameName": "7"
  },
  {
    "faceAmount": 10,
    "gameName": "中国红"
  },
  {
    "faceAmount": 10,
    "gameName": "锦鲤"
  },
  {
    "faceAmount": 20,
    "gameName": "锦鲤"
  },
  {
    "faceAmount": 20,
    "gameName": "中国红"
  },
  {
    "faceAmount": 10,
    "gameName": "大满贯"
  },
  {
    "faceAmount": 20,
    "gameName": "大满贯"
  },
  {
    "faceAmount": 50,
    "gameName": "大满贯"
  },
  {
    "faceAmount": 30,
    "gameName": "一家亲"
  },
  {
    "faceAmount": 10,
    "gameName": "上冰雪 逐梦亚冬会"
  },
  {
    "faceAmount": 5,
    "gameName": "冰城夏都"
  },
  {
    "faceAmount": 20,
    "gameName": "这么近 那么美 周末到河北"
  },
  {
    "faceAmount": 5,
    "gameName": "巳蛇"
  },
  {
    "faceAmount": 30,
    "gameName": "抢头彩2025"
  },
  {
    "faceAmount": 50,
    "gameName": "新春大吉2025"
  },
  {
    "faceAmount": 20,
    "gameName": "灵蛇献瑞"
  },
  {
    "faceAmount": 10,
    "gameName": "灵蛇贺岁"
  },
  {
    "faceAmount": 10,
    "gameName": "红包来啦 让好事发生2025"
  },
  {
    "faceAmount": 20,
    "gameName": "世运到 好运来"
  },
  {
    "faceAmount": 5,
    "gameName": "世运同行 好运连连"
  },
  {
    "faceAmount": 5,
    "gameName": "好运加满"
  },
  {
    "faceAmount": 10,
    "gameName": "筑梦大湾区"
  },
  {
    "faceAmount": 20,
    "gameName": "多彩天津"
  },
  {
    "faceAmount": 20,
    "gameName": "中国茶 武夷岩茶"
  },
  {
    "faceAmount": 10,
    "gameName": "共富浙江 名镇古村篇"
  },
  {
    "faceAmount": 10,
    "gameName": "共富浙江 场馆蝶变篇"
  },
  {
    "faceAmount": 10,
    "gameName": "新时代 新北京"
  },
  {
    "faceAmount": 20,
    "gameName": "畅游新疆 环塔拉力赛"
  },
  {
    "faceAmount": 10,
    "gameName": "行大运"
  },
  {
    "faceAmount": 20,
    "gameName": "行大运"
  },
  {
    "faceAmount": 30,
    "gameName": "行大运"
  },
  {
    "faceAmount": 50,
    "gameName": "行大运"
  },
  {
    "faceAmount": 20,
    "gameName": "麒麟王"
  },
  {
    "faceAmount": 10,
    "gameName": "好运全开"
  },
  {
    "faceAmount": 20,
    "gameName": "激情全运"
  },
  {
    "faceAmount": 20,
    "gameName": "丝路珍宝"
  },
  {
    "faceAmount": 20,
    "gameName": "亮丽内蒙古·北疆文化"
  },
  {
    "faceAmount": 20,
    "gameName": "嘶嘶大闯关"
  },
  {
    "faceAmount": 20,
    "gameName": "好客山东"
  },
  {
    "faceAmount": 20,
    "gameName": "跃动长安"
  },
  {
    "faceAmount": 10,
    "gameName": "体育科普 即刻出彩Ⅱ"
  },
  {
    "faceAmount": 10,
    "gameName": "珍稀宝贝"
  },
  {
    "faceAmount": 10,
    "gameName": "说走就走Ⅲ"
  },
  {
    "faceAmount": 10,
    "gameName": "全民健身 我来啦Ⅲ"
  },
  {
    "faceAmount": 10,
    "gameName": "八段锦"
  },
  {
    "faceAmount": 10,
    "gameName": "一路向海"
  },
  {
    "faceAmount": 50,
    "gameName": "万里长城"
  },
  {
    "faceAmount": 20,
    "gameName": "宝葫芦"
  },
  {
    "faceAmount": 30,
    "gameName": "狮王争霸"
  },
  {
    "faceAmount": 2,
    "gameName": "有礼了Ⅱ"
  },
  {
    "faceAmount": 10,
    "gameName": "去户外 动出彩"
  },
  {
    "faceAmount": 10,
    "gameName": "享赛事 品美食"
  },
  {
    "faceAmount": 10,
    "gameName": "得所愿"
  },
  {
    "faceAmount": 20,
    "gameName": "得所愿"
  },
  {
    "faceAmount": 50,
    "gameName": "得所愿"
  },
  {
    "faceAmount": 20,
    "gameName": "厦门马拉松 城市之光"
  },
  {
    "faceAmount": 10,
    "gameName": "步步登高"
  },
  {
    "faceAmount": 10,
    "gameName": "步步登高"
  },
  {
    "faceAmount": 20,
    "gameName": "为中国力量加油 雪舞龙腾"
  },
  {
    "faceAmount": 5,
    "gameName": "午马"
  },
  {
    "faceAmount": 30,
    "gameName": "抢头彩2026"
  },
  {
    "faceAmount": 50,
    "gameName": "新春大吉2026"
  },
  {
    "faceAmount": 20,
    "gameName": "马到成功"
  },
  {
    "faceAmount": 10,
    "gameName": "骏马贺岁"
  },
  {
    "faceAmount": 10,
    "gameName": "浙里烟火气"
  },
  {
    "faceAmount": 50,
    "gameName": "新春大吉2026"
  },
  {
    "faceAmount": 20,
    "gameName": "马到成功"
  },
  {
    "faceAmount": 10,
    "gameName": "骏马贺岁"
  },
  {
    "faceAmount": 5,
    "gameName": "甜蜜蜜"
  }
]

# ---------- 工具函数 ----------
def sanitize_filename(name):
    """替换文件名中不允许的字符为下划线"""
    return re.sub(r'[\\/*?:"<>|]', '_', name)

# ---------- 创建会话，支持重试 ----------
session = requests.Session()
retry = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
adapter = HTTPAdapter(max_retries=retry)
session.mount('http://', adapter)
session.mount('https://', adapter)

# ---------- 主循环 ----------
total = len(params_list)
for idx, item in enumerate(params_list, start=1):
    game_name = item['gameName']
    face_amount = item['faceAmount']

    # URL 固定，参数通过 params 传递（会自动 URL 编码）
    url = "https://sleye-mobile.lottery.cn/ubmscreen-jk-new/api/jk/downloadImage"
    params = {
        "gameName": game_name,
        "faceAmount": face_amount
    }

    print(f"[{idx}/{total}] 正在下载: {game_name} - {face_amount}")

    try:
        # 使用 POST 方法，带查询参数，请求体为空
        response = session.post(url, params=params, headers=HEADERS, timeout=30)
        response.raise_for_status()

        # 根据 Content-Type 确定扩展名
        content_type = response.headers.get('Content-Type', '')

        # 生成文件名：游戏名-面值.扩展名
        safe_game = sanitize_filename(game_name)
        if not safe_game.strip():
            safe_game = f"image_{idx}"  # 万一游戏名为空
        filename = f"{safe_game}-{face_amount}.png"
        filepath = os.path.join(DOWNLOAD_DIR, filename)

        with open(filepath, 'wb') as f:
            f.write(response.content)

        print(f"    保存为: {filename}")
    except Exception as e:
        print(f"    下载失败: {e}")

    # 适当延迟，避免请求过快
    time.sleep(0.5)

print("所有下载任务完成！")