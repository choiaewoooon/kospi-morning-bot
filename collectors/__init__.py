"""데이터 수집 모듈"""
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class MarketData:
    """주가 지수/ETF 데이터"""
    ticker: str = ""
    name: str = ""
    close: float | None = None
    change_pct: float | None = None
    open: float | None = None
    high: float | None = None
    low: float | None = None
    volume: int | None = None
    ohlc_data: list = field(default_factory=list)  # 차트용 OHLC 리스트
    fetched: bool = False


@dataclass
class NewsItem:
    """뉴스 아이템"""
    title: str
    source: str
    url: str
    published_at: datetime
    description: str = ""


from collectors.nasdaq_collector import NasdaqCollector
from collectors.koru_collector import KoruCollector
from collectors.ewy_collector import EwyCollector
from collectors.news_collector import NewsCollector
