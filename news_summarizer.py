"""
뉴스 요약 + 코스피 전망 모듈
Claude CLI 헤드리스로 밤사이 뉴스를 요약하고 코스피 전망 코멘트를 생성합니다.
"""
import asyncio
import logging

from collectors import MarketData, NewsItem
import db

logger = logging.getLogger(__name__)


async def summarize_news(
    news_items: list[NewsItem],
    nasdaq: MarketData,
    koru: MarketData,
    ewy: MarketData | None = None,
) -> str:
    """뉴스 요약 + 코스피 전망 코멘트 생성 (HTML)"""

    if not news_items and not nasdaq.fetched:
        return ""

    # 뉴스 원문 텍스트
    news_lines = []
    for i, item in enumerate(news_items[:20]):
        news_lines.append(
            f"[{i+1}] [{item.source}] {item.title}"
            f"{(' - ' + item.description[:200]) if item.description else ''}"
            f" (URL: {item.url})"
        )
    news_text = "\n".join(news_lines) if news_lines else "(수집된 뉴스 없음)"

    # 시장 데이터 텍스트
    market_text = ""
    if nasdaq.fetched and nasdaq.close:
        market_text += f"나스닥: {nasdaq.close:,.2f}"
        if nasdaq.change_pct is not None:
            market_text += f" ({nasdaq.change_pct:+.2f}%)"
        market_text += "\n"
    if koru.fetched and koru.close:
        market_text += f"$KORU (한국 3배 레버리지 ETF): ${koru.close:,.2f}"
        if koru.change_pct is not None:
            market_text += f" ({koru.change_pct:+.2f}%)"
        market_text += "\n"
    if ewy and ewy.fetched and ewy.close:
        market_text += f"$EWY (한국 ETF): ${ewy.close:,.2f}"
        if ewy.change_pct is not None:
            market_text += f" ({ewy.change_pct:+.2f}%)"

    # 과거 적중률 데이터
    accuracy_text = ""
    try:
        stats = await db.get_accuracy(14)
        if stats["total"] > 0:
            accuracy_text = f"\n과거 예측 성적 (최근 {stats['total']}일): 적중률 {stats['rate']:.0f}% ({stats['correct']}/{stats['total']})"
            # 틀린 케이스 피드백
            misses = [r for r in stats["records"] if not r["correct"] and r.get("miss_reason")]
            if misses:
                accuracy_text += "\n최근 틀린 케이스:"
                for m in misses[:3]:
                    accuracy_text += (
                        f"\n- {m['date']}: 나스닥 {m.get('nasdaq_pct', '?')}% → "
                        f"예측 {m['predicted_direction']} → 실제 {m['actual_direction']} "
                        f"(원인: {m['miss_reason']})"
                    )
    except Exception:
        pass

    prompt = f"""너는 뉴스 요약 엔진이다. 아래 데이터를 참고해서 출력 형식에 맞게만 출력해라.
헤더, 날짜, 가격 데이터, 인사말, 설명 등 절대 출력하지 마라. 오직 요청한 형식만 출력해라.

참고 데이터:
{market_text}
{accuracy_text}

밤사이 뉴스:
{news_text}

출력 형식 (이것만 출력해라, 다른 것 절대 금지):

· 뉴스요약1 <a href="URL">원문</a>
· 뉴스요약2 <a href="URL">원문</a>
· 뉴스요약3 <a href="URL">원문</a>

코스피 전망 한두줄

규칙:
- 코스피에 영향 줄 만한 뉴스 3~5개만 요약
- HTML 태그만 사용 (<b>, <a href="URL">텍스트</a>). 마크다운 금지
- 각 항목 앞에 · 사용, 각 항목 끝에 원문 링크
- 뉴스 요약 끝나고 빈 줄 하나 띄우고 코스피 전망 코멘트 1-2문장
- 나스닥/KORU/EWY 근거로 코스피 방향 예측. 과거 틀린 패턴 있으면 참고
- 톤: 반말 구어체 (~됨/~함/~인 듯), 건조하게, 이모지 최소한
- 위 출력 형식 외에 절대 아무것도 추가하지 마라"""

    try:
        process = await asyncio.create_subprocess_exec(
            "/Users/choejaewon/.local/bin/gemq", "pro", prompt,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            logger.error(f"gemq 호출 실패: {stderr.decode()}")
            return _fallback_format(news_items)

        summary = stdout.decode().strip()
        logger.info(f"뉴스 요약 완료 ({len(summary)} chars)")
        return summary

    except FileNotFoundError:
        logger.warning("claude CLI를 찾을 수 없습니다. 기본 포맷으로 대체합니다.")
        return _fallback_format(news_items)
    except Exception as e:
        logger.error(f"뉴스 요약 실패: {e}")
        return _fallback_format(news_items)


def _fallback_format(news_items: list[NewsItem]) -> str:
    """Claude 실패 시 기본 포맷"""
    lines = []
    for item in news_items[:5]:
        title = item.title.replace("<", "&lt;").replace(">", "&gt;")
        if len(title) > 120:
            title = title[:117] + "..."
        lines.append(f"· {title}")
    return "\n".join(lines)
