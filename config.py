"""
코스피 모닝브리핑 봇 - 설정 파일
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID", "")

# 뉴스 수집
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY", "")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "")

# 트위터 뉴스 계정
TWITTER_NEWS_ACCOUNTS = ["business", "Reuters", "CNBC", "axios"]

# yfinance 티커
NASDAQ_TICKER = "^IXIC"
KORU_TICKER = "KORU"
EWY_TICKER = "EWY"

# RSS 피드 (외신)
RSS_FEEDS = [
    "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml",
    "https://feeds.bbci.co.uk/news/business/rss.xml",
]

# 스케줄
SCHEDULE_HOUR = int(os.getenv("SCHEDULE_HOUR", "8"))
SCHEDULE_MINUTE = int(os.getenv("SCHEDULE_MINUTE", "40"))
TIMEZONE = os.getenv("TIMEZONE", "Asia/Seoul")

# 뉴스 수집 범위 (시간)
NEWS_LOOKBACK_START_HOUR = 18  # 전날 18시부터
NEWS_LOOKBACK_END_MINUTE_BEFORE = 20  # 발송 20분 전까지 (08:20)
