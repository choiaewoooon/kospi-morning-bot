"""
텔레그램 메시지 포매터
"""
from datetime import datetime
from zoneinfo import ZoneInfo

from collectors import MarketData
import config


def _fmt_price(n: float | None, prefix: str = "") -> str:
    if n is None:
        return "N/A"
    if n >= 1000:
        return f"{prefix}{n:,.2f}"
    return f"{prefix}{n:.2f}"


def build_morning_report(
    nasdaq: MarketData,
    koru: MarketData,
    ewy: MarketData,
    news_summary: str = "",
) -> str:
    """모닝브리핑 텔레그램 메시지 생성 (HTML)"""

    kst = ZoneInfo(config.TIMEZONE)
    now = datetime.now(kst)
    date_str = now.strftime("%Y.%m.%d %a")

    lines = []

    # 헤더
    lines.append(f"<b>코스피 모닝브리핑 | {date_str}</b>")
    lines.append("")

    # 나스닥
    if nasdaq.fetched and nasdaq.close:
        pct = nasdaq.change_pct
        if pct is not None:
            arrow = "+" if pct >= 0 else ""
            lines.append(
                f"<b>나스닥 {_fmt_price(nasdaq.close)}</b>"
                f"  ({arrow}{pct:.2f}%)"
            )
        else:
            lines.append(f"<b>나스닥 {_fmt_price(nasdaq.close)}</b>")
    else:
        lines.append("나스닥 데이터 수집 실패")

    # $KORU
    if koru.fetched and koru.close:
        pct = koru.change_pct
        if pct is not None:
            arrow = "+" if pct >= 0 else ""
            lines.append(
                f"<b>$KORU {_fmt_price(koru.close, '$')}</b>"
                f"  ({arrow}{pct:.2f}%)"
            )
        else:
            lines.append(f"<b>$KORU {_fmt_price(koru.close, '$')}</b>")
    else:
        lines.append("$KORU 데이터 수집 실패")

    # $EWY
    if ewy.fetched and ewy.close:
        pct = ewy.change_pct
        if pct is not None:
            arrow = "+" if pct >= 0 else ""
            lines.append(
                f"<b>$EWY {_fmt_price(ewy.close, '$')}</b>"
                f"  ({arrow}{pct:.2f}%)"
            )
        else:
            lines.append(f"<b>$EWY {_fmt_price(ewy.close, '$')}</b>")
    else:
        lines.append("$EWY 데이터 수집 실패")

    lines.append("")

    # 뉴스 요약 + 코멘트 분리
    if news_summary:
        # 빈 줄 기준으로 뉴스 파트와 코멘트 파트 분리
        parts = news_summary.split("\n\n", 1)
        news_part = parts[0].strip()
        comment_part = parts[1].strip() if len(parts) > 1 else ""

        lines.append("<b>\U0001f5de\ufe0f 밤사이 주요 뉴스</b>")
        lines.append(f"<blockquote>{news_part}</blockquote>")

        if comment_part:
            lines.append("")
            lines.append("<b>\U0001f4ca 코스피 예상 코멘트</b>")
            lines.append(f"<blockquote>{comment_part}</blockquote>")

    return "\n".join(lines)
