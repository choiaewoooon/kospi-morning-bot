"""
밤사이 뉴스 수집 (NewsAPI + Twitter + RSS)
"""
import asyncio
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

import httpx

import config
from collectors import NewsItem

logger = logging.getLogger(__name__)

NEWSAPI_URL = "https://newsapi.org/v2/everything"
RAPIDAPI_HOST = "twitter-api45.p.rapidapi.com"
TIMELINE_URL = f"https://{RAPIDAPI_HOST}/timeline.php"


class NewsCollector:
    """뉴스 수집기"""

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=15)

    async def collect(self) -> list[NewsItem]:
        """밤사이 뉴스 수집 (전날 18:00 ~ 당일 08:20 KST)"""
        kst = ZoneInfo(config.TIMEZONE)
        now = datetime.now(kst)
        cutoff_end = now.replace(hour=8, minute=20, second=0, microsecond=0)
        cutoff_start = (now - timedelta(days=1)).replace(
            hour=config.NEWS_LOOKBACK_START_HOUR, minute=0, second=0, microsecond=0
        )

        news_items = []

        # NewsAPI 수집
        newsapi_items = await self._collect_newsapi(cutoff_start, cutoff_end)
        news_items.extend(newsapi_items)

        # Twitter 수집
        twitter_items = await self._collect_twitter(cutoff_start, cutoff_end)
        news_items.extend(twitter_items)

        # RSS 피드 수집
        rss_items = await self._collect_rss(cutoff_start, cutoff_end)
        news_items.extend(rss_items)

        # 중복 제거 (제목 기준)
        seen_titles = set()
        unique_items = []
        for item in news_items:
            key = item.title[:80].lower()
            if key not in seen_titles:
                seen_titles.add(key)
                unique_items.append(item)
        news_items = unique_items

        # 시간순 정렬 (최신 먼저)
        news_items.sort(key=lambda x: x.published_at, reverse=True)
        logger.info(f"뉴스 총 {len(news_items)}건 수집 완료")
        return news_items

    async def _collect_newsapi(
        self, start: datetime, end: datetime
    ) -> list[NewsItem]:
        """NewsAPI에서 뉴스 수집"""
        if not config.NEWSAPI_KEY:
            logger.warning("NEWSAPI_KEY 미설정, NewsAPI 건너뜀")
            return []

        items = []
        keywords = [
            "나스닥 OR NASDAQ OR 코스피 OR 반도체 OR semiconductor",
            "연준 OR Fed OR 금리 OR interest rate",
        ]

        for query in keywords:
            try:
                resp = await self.client.get(
                    NEWSAPI_URL,
                    params={
                        "q": query,
                        "from": start.strftime("%Y-%m-%dT%H:%M:%S"),
                        "to": end.strftime("%Y-%m-%dT%H:%M:%S"),
                        "sortBy": "relevancy",
                        "pageSize": 10,
                        "apiKey": config.NEWSAPI_KEY,
                    },
                )
                resp.raise_for_status()
                data = resp.json()

                for article in data.get("articles", []):
                    pub = article.get("publishedAt", "")
                    try:
                        published_at = datetime.fromisoformat(
                            pub.replace("Z", "+00:00")
                        )
                    except (ValueError, AttributeError):
                        continue

                    items.append(
                        NewsItem(
                            title=article.get("title", ""),
                            source=article.get("source", {}).get("name", ""),
                            url=article.get("url", ""),
                            published_at=published_at,
                            description=article.get("description", "") or "",
                        )
                    )

            except Exception as e:
                logger.error(f"NewsAPI 수집 실패 ({query[:20]}...): {e}")

        logger.info(f"NewsAPI: {len(items)}건 수집")
        return items

    async def _collect_twitter(
        self, start: datetime, end: datetime
    ) -> list[NewsItem]:
        """Twitter에서 뉴스 계정 트윗 수집"""
        if not config.RAPIDAPI_KEY:
            logger.warning("RAPIDAPI_KEY 미설정, Twitter 뉴스 건너뜀")
            return []

        items = []
        headers = {
            "x-rapidapi-host": RAPIDAPI_HOST,
            "x-rapidapi-key": config.RAPIDAPI_KEY,
        }

        for account in config.TWITTER_NEWS_ACCOUNTS:
            try:
                resp = await self.client.get(
                    TIMELINE_URL,
                    params={"screenname": account},
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()

                for tw in data.get("timeline", []):
                    try:
                        created_at = parsedate_to_datetime(tw["created_at"])
                    except (KeyError, ValueError):
                        continue

                    if created_at < start.astimezone(timezone.utc):
                        continue
                    if created_at > end.astimezone(timezone.utc):
                        continue

                    items.append(
                        NewsItem(
                            title=tw.get("text", ""),
                            source=f"@{account}",
                            url=f"https://x.com/{account}/status/{tw.get('tweet_id', '')}",
                            published_at=created_at,
                        )
                    )

                await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"@{account} 트윗 수집 실패: {e}")

        logger.info(f"Twitter: {len(items)}건 수집")
        return items

    async def _collect_rss(
        self, start: datetime, end: datetime
    ) -> list[NewsItem]:
        """RSS 피드에서 뉴스 수집"""
        items = []

        for feed_url in config.RSS_FEEDS:
            try:
                resp = await self.client.get(feed_url)
                resp.raise_for_status()
                root = ET.fromstring(resp.text)

                for item_el in root.iter("item"):
                    title = item_el.findtext("title", "")
                    link = item_el.findtext("link", "")
                    pub_date = item_el.findtext("pubDate", "")
                    description = item_el.findtext("description", "") or ""

                    if not title or not pub_date:
                        continue

                    try:
                        published_at = parsedate_to_datetime(pub_date)
                    except (ValueError, TypeError):
                        continue

                    if published_at < start.astimezone(timezone.utc):
                        continue
                    if published_at > end.astimezone(timezone.utc):
                        continue

                    # 소스 이름 추출
                    source = "RSS"
                    if "reuters" in feed_url:
                        source = "Reuters"
                    elif "nytimes" in feed_url:
                        source = "NYTimes"
                    elif "bloomberg" in feed_url:
                        source = "Bloomberg"

                    items.append(
                        NewsItem(
                            title=title,
                            source=source,
                            url=link,
                            published_at=published_at,
                            description=description[:300],
                        )
                    )

            except Exception as e:
                logger.error(f"RSS 수집 실패 ({feed_url[:40]}...): {e}")

        logger.info(f"RSS: {len(items)}건 수집")
        return items

    async def close(self):
        await self.client.aclose()
