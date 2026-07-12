# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/config/base_config.py
# GitHub: https://github.com/NanmiCoder
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#

# 声明：本代码仅供学习和研究目的使用。使用者应遵守以下原则：
# 1. 不得用于任何商业用途。
# 2. 使用时应遵守目标平台的使用条款和robots.txt规则。
# 3. 不得进行大规模爬取或对平台造成运营干扰。
# 4. 应合理控制请求频率，避免给目标平台带来不必要的负担。
# 5. 不得用于任何非法或不当的用途。
#
# 详细许可条款请参阅项目根目录下的LICENSE文件。
# 使用本代码即表示您同意遵守上述原则和LICENSE中的所有条款。

# Basic configuration
PLATFORM = "xhs"  # Platform, xhs | dy | ks | bili | wb | tieba | zhihu

# 是否使用海外版小红书 (rednote.com)
# 开启后 API 走 webapi.rednote.com，cookie 域使用 .rednote.com
XHS_INTERNATIONAL = False

KEYWORDS = "编程副业,编程兼职"  # Keyword search configuration, separated by English commas
LOGIN_TYPE = "qrcode"  # qrcode or phone or cookie
COOKIES = ""
CRAWLER_TYPE = (
    "search"  # Crawling type, search (keyword search) | detail (post details) | creator (creator homepage data)
)
# Whether to enable IP proxy
ENABLE_IP_PROXY = False

# Number of proxy IP pools
IP_PROXY_POOL_COUNT = 2

# Proxy IP provider name
IP_PROXY_PROVIDER_NAME = "kuaidaili"  # kuaidaili | wandouhttp | static

# Static proxy configuration (used when IP_PROXY_PROVIDER_NAME is set to "static")
# Format: "http://your_home_domain:port" or "http://user:password@your_home_domain:port"
STATIC_PROXY_URL = ""

# Setting to True will not open the browser (headless browser)
# Setting False will open a browser
# If Xiaohongshu keeps scanning the code to log in but fails, open the browser and manually pass the sliding verification code.
# If Douyin keeps prompting failure, open the browser and see if mobile phone number verification appears after scanning the QR code to log in. If it does, manually go through it and try again.
HEADLESS = False

# Whether to save login status
SAVE_LOGIN_STATE = True

# ==================== CDP (Chrome DevTools Protocol) 配置 ====================
# 是否启用 CDP 模式 - 使用用户本地的 Chrome/Edge 浏览器进行爬取，具有更好的反检测能力
# 开启后，会自动检测并启动用户的 Chrome/Edge 浏览器，通过 CDP 协议进行控制
# 该方式使用真实浏览器环境，包括用户的扩展、Cookie 和设置，大幅降低被风控检测的风险
ENABLE_CDP_MODE = True

# CDP 调试端口，用于与浏览器通信
# 如果端口被占用，系统会自动尝试下一个可用端口
CDP_DEBUG_PORT = 9222

# 自定义浏览器路径（可选）
# 如果为空，系统会自动检测 Chrome/Edge 的安装路径
# Windows 示例: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
# macOS 示例: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
CUSTOM_BROWSER_PATH = ""

# 是否在 CDP 模式下启用无头模式
# 注意：即使设置为 True，某些反检测功能在无头模式下可能无法正常工作
CDP_HEADLESS = False

# 浏览器启动超时时间（秒）
BROWSER_LAUNCH_TIMEOUT = 60

# 是否连接用户已打开的浏览器，而不是启动新的浏览器
# 开启后，程序会连接一个已经启用了远程调试的浏览器
# 用户需要在 Chrome 中开启远程调试：chrome://inspect/#remote-debugging
# 或者使用命令行参数启动 Chrome：--remote-debugging-port=9222
# 这种方式反检测效果最好，因为直接使用用户真实浏览器的所有 Cookie、扩展和浏览历史
CDP_CONNECT_EXISTING = True

# 程序结束时是否自动关闭浏览器
# 设置为 False 可以保持浏览器运行，方便调试
AUTO_CLOSE_BROWSER = True

# Data saving type option configuration, supports: csv, db, json, jsonl, sqlite, excel, postgres. It is best to save to DB, with deduplication function.
SAVE_DATA_OPTION = "jsonl"  # csv or db or json or jsonl or sqlite or excel or postgres

# Data saving path, if not specified by default, it will be saved to the data folder.
SAVE_DATA_PATH = ""

# Browser file configuration cached by the user's browser
USER_DATA_DIR = "%s_user_data_dir"  # %s will be replaced by platform name

# The number of pages to start crawling starts from the first page by default
START_PAGE = 1

# Control the number of crawled videos/posts
CRAWLER_MAX_NOTES_COUNT = 15

# Controlling the number of concurrent crawlers
MAX_CONCURRENCY_NUM = 1

# Whether to enable crawling media mode (including image or video resources), crawling media is not enabled by default
ENABLE_GET_MEIDAS = False

# Whether to enable comment crawling mode. Comment crawling is enabled by default.
ENABLE_GET_COMMENTS = True

# Control the number of crawled first-level comments (single video/post)
CRAWLER_MAX_COMMENTS_COUNT_SINGLENOTES = 10

# Whether to enable the mode of crawling second-level comments. By default, crawling of second-level comments is not enabled.
# If the old version of the project uses db, you need to refer to schema/tables.sql line 287 to add table fields.
ENABLE_GET_SUB_COMMENTS = False

# word cloud related
# Whether to enable generating comment word clouds
ENABLE_GET_WORDCLOUD = False
# Custom words and their groups
# Add rule: xx:yy where xx is a custom-added phrase, and yy is the group name to which the phrase xx is assigned.
CUSTOM_WORDS = {
    "零几": "年份",  # Recognize "zero points" as a whole
    "高频词": "专业术语",  # Example custom words
}

# Deactivate (disabled) word file path
STOP_WORDS_FILE = "./docs/hit_stopwords.txt"

# Chinese font file path
FONT_PATH = "./docs/STZHONGS.TTF"

# Crawl interval
CRAWLER_MAX_SLEEP_SEC = 2

# 是否禁用 SSL 证书验证。仅在使用企业代理、Burp Suite、mitmproxy 等会注入自签名证书的中间人代理时设为 True。
# 警告：禁用 SSL 验证将使所有流量暴露于中间人攻击风险，请勿在生产环境中开启。
DISABLE_SSL_VERIFY = False

# ==================== 签名服务 (SignSrv) 配置 ====================
# 将各平台签名算法(execjs + JS / 纯 Python)解耦为独立 HTTP 微服务 (sign_service/app.py)，
# crawler 主进程无需安装 Node 运行时即可签名。
#
# 启用步骤:
#   1. 启动签名服务: uv run uvicorn sign_service.app:app --port 8888
#   2. 将 ENABLE_SIGN_SERVICE 设为 True
# 若服务未启动或不可达,会自动 fallback 到各平台原有的本地签名函数,功能不中断。
ENABLE_SIGN_SERVICE = False
SIGN_SERVICE_URL = "http://127.0.0.1:8888"

# ==================== 断点续爬 (Resume) 配置 ====================
# 启用后,爬虫会把进度(已抓到第几页、search_id、已处理 note_id)持久化到
# database/checkpoints.db(独立 sqlite,不依赖 SAVE_DATA_OPTION)。
# 中断后可用 --resume <task_id> 从断点继续,避免重复抓取。
# 首次运行会生成 task_id 并打印,便于后续续爬。
ENABLE_RESUME = False
RESUME_TASK_ID = ""  # 续爬时填入上次任务的 task_id

# ==================== 多账号 (Account Pool) 配置 ====================
# 启用后,crawler 会从账号池(database/accounts.db)轮转使用多个账号,
# 每账号独立 user_data_dir 与可选代理,失败自动切换。详见 account/README.md
ENABLE_ACCOUNT_POOL = False
ACCOUNT_POOL_FAIL_THRESHOLD = 3   # 连续失败次数达此值,账号进入冷却
ACCOUNT_CONCURRENCY = 1           # 同时使用几个账号(1=串行轮转,>1=并发)
ACCOUNTS_IMPORT_FILE = ""         # 启动时从该 CSV/Excel 导入账号(可选)

# ==================== 脱浏览器模式 (Headless API) 配置 ====================
# 当前生效平台:xhs / zhihu(签名均为纯算法,无需 page.evaluate)。
# 开启后,若已有 cookie(来自 config.COOKIES 或账号池),这些平台会跳过浏览器启动,
# 直接用 httpx + 签名服务完成请求,大幅降低资源占用(无 playwright/CDP)。
# 无 cookie 时仍走 CDP 登录拿 cookie。
# 注:bilibili(需浏览器 localStorage 的 wbi keys)、tieba(PC API 经 page.evaluate fetch)、
# 抖音/微博/快手 仍需浏览器,不适用本模式。
ENABLE_HEADLESS_API = False

# ==================== 反检测 (Anti-Detect) 配置 ====================
# 降低被平台识别为机器人的风险。详见 anti_detect/README.md
# 重要:这些措施只能降低风险,不能保证零风险。请用小号 + 控制规模 + 遵守平台规则。
# 是否启用反检测(总开关)。关闭后下面所有子项失效,crawler 恢复原行为。
ENABLE_ANTI_DETECT = False
# 行为拟人化:固定 sleep 改为 sleep(base + random(0, jitter))
HUMANIZE_SLEEP_JITTER = 3      # 随机抖动秒数(加在 CRAWLER_MAX_SLEEP_SEC 上)
HUMANIZE_PAGE_STAY_SEC = 3     # 进入页面后停留秒数(模拟阅读)
HUMANIZE_SCROLL_TIMES = 3      # 页面滚动次数(模拟浏览)
# 截图风控感知:每页请求后截图 → OCR/LLM 识别风控页面
ANTI_DETECT_SCREENSHOT = True  # 是否截图做风控判定
ANTI_DETECT_SCREENSHOT_DIR = "data/risk_screenshots"  # 截图保存目录
# OCR 通道(优先):用 RapidOCR(ppocr)提取截图文字 → 关键词判定。纯本地零成本。
# 安装: pip install rapidocr-onnxruntime (或 uv add rapidocr-onnxruntime)
# 未安装时自动 fallback 到 LLM 截图多模态识别。
ANTI_DETECT_USE_OCR = True
# 风控响应:检测到风控时的处理策略(stop=停止 | backoff=退避重试)
ANTI_DETECT_ON_RISK = "stop"
# 智能退避:连续风控时的退避参数
ANTI_DETECT_BACKOFF_BASE = 60    # 首次退避秒数
ANTI_DETECT_BACKOFF_MAX = 1800   # 最大退避秒数(30分钟)
ANTI_DETECT_RISK_LIMIT = 3       # 连续风控达此数 → 停止该账号
# 滑块自动通过:复用 tools/slider_util.py 的 opencv 识别
ANTI_DETECT_AUTO_SLIDER = False  # 是否自动尝试过滑块(成功率有限,谨慎开启)

# ==================== 好房雷达(house_pro)对接配置 ====================
# MediaCrawler 采集后,额外把结构化 Listing 数据写到 house_pro 期望的目录,
# house_pro 的 Celery 定时扫该目录做 ETL 入库。
# 设为空字符串则不启用文件落盘(只用 HTTP API 对接)。
HOUSE_RAW_DIR = ""  # 如 "../house_pro/data/xhs_raw"

from .bilibili_config import *
from .xhs_config import *
from .dy_config import *
from .ks_config import *
from .weibo_config import *
from .tieba_config import *
from .zhihu_config import *
from .douban_config import *
