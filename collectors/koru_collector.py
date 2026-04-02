"""
$KORU ETF 수집 (yfinance)
Direxion Daily MSCI South Korea Bull 3X ETF
"""
import logging

import yfinance as yf

import config
from collectors import MarketData

logger = logging.getLogger(__name__)


class KoruCollector:
    """$KORU ETF 수집기"""

    async def collect(self) -> MarketData:
        """KORU 종가, 변동률, OHLC 데이터 수집"""
        data = MarketData(ticker=config.KORU_TICKER, name="$KORU")

        try:
            ticker = yf.Ticker(config.KORU_TICKER)
            hist = ticker.history(period="5d", interval="1h")

            if hist.empty:
                logger.error("$KORU 데이터 없음")
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

            # 차트용 OHLC
            today = daily.index[-1].date() if not daily.empty else None
            if today and not hist.empty:
                day_data = hist[hist.index.date == today]
                if day_data.empty:
                    day_data = hist.tail(8)
                data.ohlc_data = [
                    {
                        "time": row.Index.isoformat(),
                        "open": row.Open,
                        "high": row.High,
                        "low": row.Low,
                        "close": row.Close,
                    }
                    for row in day_data.itertuples()
                ]

            data.fetched = True
            logger.info(
                f"$KORU 수집 완료: ${data.close:,.2f} ({data.change_pct:+.2f}%)"
                if data.close and data.change_pct is not None
                else "$KORU 수집 완료 (변동률 없음)"
            )

        except Exception as e:
            logger.error(f"$KORU 수집 실패: {e}")

        return data
