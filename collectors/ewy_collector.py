"""
$EWY ETF 수집 (yfinance)
iShares MSCI South Korea ETF
"""
import logging

import yfinance as yf

import config
from collectors import MarketData

logger = logging.getLogger(__name__)


class EwyCollector:
    """$EWY ETF 수집기"""

    async def collect(self) -> MarketData:
        """EWY 종가, 변동률, OHLC 데이터 수집"""
        data = MarketData(ticker=config.EWY_TICKER, name="$EWY")

        try:
            ticker = yf.Ticker(config.EWY_TICKER)
            hist = ticker.history(period="5d", interval="1h")

            if hist.empty:
                logger.error("$EWY 데이터 없음")
                return data

            daily = ticker.history(period="2d")
            if len(daily) >= 2:
                data.close = daily["Close"].iloc[-1]
                prev_close = daily["Close"].iloc[-2]
                data.change_pct = (data.close - prev_close) / prev_close * 100
            elif len(daily) == 1:
                data.close = daily["Close"].iloc[-1]

            data.open = daily["Open"].iloc[-1] if not daily.empty else None
            data.high = daily["High"].iloc[-1] if not daily.empty else None
            data.low = daily["Low"].iloc[-1] if not daily.empty else None
            data.volume = int(daily["Volume"].iloc[-1]) if not daily.empty else None

            data.fetched = True
            logger.info(
                f"$EWY 수집 완료: ${data.close:,.2f} ({data.change_pct:+.2f}%)"
                if data.close and data.change_pct is not None
                else "$EWY 수집 완료 (변동률 없음)"
            )

        except Exception as e:
            logger.error(f"$EWY 수집 실패: {e}")

        return data
