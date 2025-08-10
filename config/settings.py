import os
from dotenv import load_dotenv
from typing import List

load_dotenv()

# --- Paths ---
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
USER_DATA_PATH = os.path.join(PROJECT_ROOT, "storage/user-session/users.json")
CHAT_HISTORY_PATH = os.path.join(PROJECT_ROOT, "storage/chat-session")
PWVN_ROLES_CONFIG_PATH = os.path.join(PROJECT_ROOT, "knowledge/roles.json")
PWVN_DIALOGS_CONFIG_PATH = os.path.join(PROJECT_ROOT, "knowledge/roles.json")
PWVN_BG_CONFIG_PATH = os.path.join(PROJECT_ROOT, "knowledge/background.txt")
PWVN_QUERY_STORE_PATH = os.path.join(PROJECT_ROOT, "storage/chunks")
PWVN_CHAT_STORE_PATH = os.path.join(PROJECT_ROOT, "storage/chat-session")

# --- Bot & Framework ---
ONEBOT_WS_URL = os.getenv("ONEBOT_WS_URL", "ws://127.0.0.1:8080")
BOT_QQ_ID = int(os.getenv("BOT_QQ_ID", 0))
ENABLED_GROUP_IDS = [
    int(gid) for gid in os.getenv("ENABLED_GROUP_IDS", "").split(',') if gid
]

# --- LLM ---
# "true" or "false"
USE_OLLAMA = os.getenv("USE_OLLAMA", "false").lower() == "true"
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# --- Admin ---
# 管理员 QQ 号列表，注意是整数
ADMIN_USER_IDS = [int(uid) for uid in os.getenv("ADMIN_USER_IDS", "").split(',') if uid]

RSS_FEEDS = {
    feed.split('|')[0]: feed.split('|')[1]
    for feed in os.getenv("RSS_FEEDS", "").split(';')
    if feed and '|' in feed
}

# 报告相关配置
NEWS_REPORT_TITLE = os.getenv("NEWS_REPORT_TITLE", "今日技术资讯摘要")
MAX_ITEMS_PER_FEED = int(os.getenv("MAX_ITEMS_PER_FEED", "3"))
MAX_TOTAL_ITEMS = int(os.getenv("MAX_TOTAL_ITEMS", "15"))
TIMEZONE = os.getenv("TIMEZONE", "Asia/Shanghai")
INCLUDE_KEYWORDS: List[str] = os.getenv("INCLUDE_KEYWORDS", "").split(',')
EXCLUDE_KEYWORDS: List[str] = os.getenv("EXCLUDE_KEYWORDS", "").split(',')
REPORT_FORMAT = os.getenv("REPORT_FORMAT", "text")
# --- Scheduler (修改以适应新闻报告) ---

NEWS_SCHEDULE_CONFIG = {
    "enabled": os.getenv("NEWS_ENABLED", "true").lower() == "true",
    "job_name": "daily_rss_report",
    "hour": 8,
    "minute": 0,
    "target_group_ids": [int(gid) for gid in os.getenv("NEWS_TARGET_GROUPS", "").split(',') if gid]
}