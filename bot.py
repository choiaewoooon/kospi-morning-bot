"""
코스피 모닝브리핑 봇 - 메인 실행 파일
매일 아침 08:40 KST에 나스닥/$KORU + 밤사이 뉴스 요약을 텔레그램 채널에 발송합니다.
15:45 KST에 코스피 종가를 수집하여 예측 검증을 수행합니다.

사용법:
  python bot.py          # 스케줄러 모드 (매일 자동 실행)
  python bot.py --now    # 즉시 1회 실행 (테스트용)
  python bot.py --verify # 즉시 검증 1회 실행 (테스트용)
"""
import asyncio
import argparse
import logging
import sys
from datetime import datetime, date
from io import BytesIO
from zoneinfo import ZoneInfo

import yfinance as yf
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Bot
from telegram.constants import ParseMode

import config
from collectors import NasdaqCollector, KoruCollector, EwyCollector, NewsCollector, MarketData
from formatter import build_morning_report
from chart_generator import generate_charts_base64
from image_generator import generate_morning_card
from news_summarizer import summarize_news
from prediction_parser import parse_direction
import db

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("kospi_bot")


async def collect_and_post():
    """데이터 수집 후 텔레그램 발송 + 예측 저장"""
    kst = ZoneInfo(config.TIMEZONE)
    now = datetime.now(kst)

    # 주말 스킵 (토=5, 일=6)
    if now.weekday() >= 5:
        logger.info(f"주말이라 브리핑 스킵 ({now.strftime('%Y-%m-%d %A')})")
        return

    logger.info(f"=== 모닝브리핑 시작 ({now.strftime('%Y-%m-%d %H:%M')}) ===")

    await db.init_db()

    nasdaq_collector = NasdaqCollector()
    koru_collector = KoruCollector()
    ewy_collector = EwyCollector()
    news_collector = NewsCollector()

    try:
        # 데이터 수집 (병렬)
        logger.info("데이터 수집 시작...")
        nasdaq, koru, ewy, news_items = await asyncio.gather(
            nasdaq_collector.collect(),
            koru_collector.collect(),
            ewy_collector.collect(),
            news_collector.collect(),
            return_exceptions=True,
        )

        # 예외 처리
        if isinstance(nasdaq, Exception):
            logger.error(f"나스닥 수집 오류: {nasdaq}")
            nasdaq = MarketData(ticker="^IXIC", name="나스닥")
        if isinstance(koru, Exception):
            logger.error(f"KORU 수집 오류: {koru}")
            koru = MarketData(ticker="KORU", name="$KORU")
        if isinstance(ewy, Exception):
            logger.error(f"EWY 수집 오류: {ewy}")
            ewy = MarketData(ticker="EWY", name="$EWY")
        if isinstance(news_items, Exception):
            logger.error(f"뉴스 수집 오류: {news_items}")
            news_items = []

        # AI 뉴스 요약 + 코스피 전망
        news_summary = await summarize_news(news_items, nasdaq, koru, ewy)

        # 예측 정확도 조회
        accuracy = await db.get_accuracy(days=30)

        # 메시지 생성
        message = build_morning_report(nasdaq, koru, ewy, news_summary, accuracy)
        logger.info(f"메시지 생성 완료 ({len(message)} chars)")

        # 예측 방향 파싱 및 DB 저장
        predicted_direction = parse_direction(news_summary)
        today = datetime.now(kst).date()
        await db.save_prediction(
            dt=today,
            nasdaq_pct=nasdaq.change_pct,
            koru_pct=koru.change_pct,
            ewy_pct=ewy.change_pct,
            predicted_direction=predicted_direction,
            prediction_comment=news_summary,
        )

        # 텔레그램 전송
        if not config.TELEGRAM_BOT_TOKEN:
            logger.error("TELEGRAM_BOT_TOKEN 미설정!")
            import re
            print(re.sub(r"<[^>]+>", "", message))
            return

        bot = Bot(token=config.TELEGRAM_BOT_TOKEN)

        if not config.TELEGRAM_CHANNEL_ID:
            logger.error("TELEGRAM_CHANNEL_ID 미설정!")
            return

        # 이미지 카드 생성
        kst_now = datetime.now(kst)
        date_str = kst_now.strftime("%Y.%m.%d %a")
        sent = False

        try:
            chart_b64 = await generate_charts_base64(nasdaq, koru)
            image_bytes = await generate_morning_card(nasdaq, koru, date_str, chart_b64)
            if image_bytes:
                await bot.send_photo(
                    chat_id=config.TELEGRAM_CHANNEL_ID,
                    photo=BytesIO(image_bytes),
                    caption=message,
                    parse_mode=ParseMode.HTML,
                )
                sent = True
                logger.info("이미지 + 텍스트 전송 완료")
        except Exception as e:
            logger.warning(f"이미지 전송 실패, 텍스트만 전송: {e}")

        if not sent:
            await bot.send_message(
                chat_id=config.TELEGRAM_CHANNEL_ID,
                text=message,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )

        logger.info(f"텔레그램 전송 완료 -> {config.TELEGRAM_CHANNEL_ID}")

    except Exception as e:
        logger.error(f"브리핑 처리 중 오류: {e}", exc_info=True)

    finally:
        await news_collector.close()

    logger.info("=== 모닝브리핑 완료 ===")


async def verify_prediction():
    """코스피 장 마감 후 예측 검증"""
    kst = ZoneInfo(config.TIMEZONE)
    today = datetime.now(kst).date()
    logger.info(f"=== 예측 검증 시작 ({today}) ===")

    await db.init_db()

    try:
        # 코스피 종가 수집
        kospi = yf.Ticker("^KS11")
        hist = kospi.history(period="2d")

        if len(hist) < 1:
            logger.error("코스피 데이터 없음, 검증 건너뜀")
            return

        kospi_close = hist["Close"].iloc[-1]
        kospi_open = hist["Open"].iloc[-1]

        if len(hist) >= 2:
            prev_close = hist["Close"].iloc[-2]
            kospi_pct = (kospi_close - prev_close) / prev_close * 100
        else:
            kospi_pct = (kospi_close - kospi_open) / kospi_open * 100

        # 실제 방향 판단
        if kospi_pct > 0.3:
            actual_direction = "up"
        elif kospi_pct < -0.3:
            actual_direction = "down"
        else:
            actual_direction = "neutral"

        # 오늘 예측 기록 가져와서 비교
        record = await db.get_prediction(today)
        if not record:
            logger.warning("오늘 예측 기록 없음")
            return

        predicted = record.get("predicted_direction", "neutral")
        correct = predicted == actual_direction

        # 틀렸을 때 원인 분석 (Claude에게 물어봄)
        miss_reason = ""
        if not correct:
            miss_reason = await _analyze_miss(record, kospi_pct, actual_direction)

        await db.update_actual(
            dt=today,
            kospi_open=kospi_open,
            kospi_close=kospi_close,
            kospi_pct=kospi_pct,
            actual_direction=actual_direction,
            correct=correct,
            miss_reason=miss_reason,
        )

        # 로그
        status = "적중" if correct else "오답"
        logger.info(
            f"코스피 {kospi_close:,.2f} ({kospi_pct:+.2f}%) | "
            f"예측: {predicted} → 실제: {actual_direction} | {status}"
        )

    except Exception as e:
        logger.error(f"검증 중 오류: {e}", exc_info=True)

    logger.info("=== 예측 검증 완료 ===")


async def _analyze_miss(record: dict, kospi_pct: float, actual: str) -> str:
    """틀린 예측의 원인 분석 (Claude CLI)"""
    try:
        prompt = f"""아래 예측이 틀렸다. 원인을 한 줄로 분석해라.

예측 근거:
- 나스닥: {record.get('nasdaq_pct', 'N/A')}%
- KORU: {record.get('koru_pct', 'N/A')}%
- EWY: {record.get('ewy_pct', 'N/A')}%
- 예측 방향: {record.get('predicted_direction')}

실제 결과:
- 코스피: {kospi_pct:+.2f}% ({actual})

한 줄로 왜 틀렸는지 써라. 예: "외국인 순매도 폭탄", "환율 급등 영향" 등."""

        process = await asyncio.create_subprocess_exec(
            "/Users/choejaewon/.local/bin/gemq", "pro", prompt,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            return stdout.decode().strip()[:200]
    except Exception as e:
        logger.error(f"오답 원인 분석 실패: {e}")

    return ""


def run_scheduler():
    """APScheduler로 매일 지정 시간에 실행"""
    kst = ZoneInfo(config.TIMEZONE)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    scheduler = AsyncIOScheduler(timezone=kst, event_loop=loop)

    # 아침 브리핑
    scheduler.add_job(
        collect_and_post,
        trigger="cron",
        hour=config.SCHEDULE_HOUR,
        minute=config.SCHEDULE_MINUTE,
        id="kospi_morning_briefing",
        name="KOSPI Morning Briefing",
        misfire_grace_time=3600,
    )

    # 오후 검증 (15:45 KST - 장 마감 후)
    scheduler.add_job(
        verify_prediction,
        trigger="cron",
        hour=15,
        minute=45,
        id="kospi_verify",
        name="KOSPI Prediction Verify",
        misfire_grace_time=3600,
        day_of_week="mon-fri",
    )

    scheduler.start()
    logger.info(
        f"스케줄러 시작: 브리핑 {config.SCHEDULE_HOUR:02d}:{config.SCHEDULE_MINUTE:02d} / 검증 15:45 KST"
    )

    try:
        loop.run_forever()
    except (KeyboardInterrupt, SystemExit):
        logger.info("봇 종료")
        scheduler.shutdown()


def main():
    parser = argparse.ArgumentParser(description="코스피 모닝브리핑 봇")
    parser.add_argument("--now", action="store_true", help="즉시 1회 실행 (테스트용)")
    parser.add_argument("--verify", action="store_true", help="즉시 검증 1회 실행 (테스트용)")
    args = parser.parse_args()

    warnings = []
    if not config.TELEGRAM_BOT_TOKEN:
        warnings.append("TELEGRAM_BOT_TOKEN 미설정")
    if not config.TELEGRAM_CHANNEL_ID:
        warnings.append("TELEGRAM_CHANNEL_ID 미설정")
    if not config.NEWSAPI_KEY:
        warnings.append("NEWSAPI_KEY 미설정 (뉴스 수집 제한)")

    for w in warnings:
        logger.warning(f"[설정] {w}")

    if args.now:
        logger.info("즉시 실행 모드")
        asyncio.run(collect_and_post())
    elif args.verify:
        logger.info("즉시 검증 모드")
        asyncio.run(verify_prediction())
    else:
        run_scheduler()


if __name__ == "__main__":
    main()
