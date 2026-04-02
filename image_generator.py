"""
모닝브리핑 데이터 카드 이미지 생성
HTML 템플릿 + Playwright 스크린샷
"""
import base64
import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from playwright.async_api import async_playwright

from collectors import MarketData

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).parent / "templates"


def _fmt_price(n: float | None, prefix: str = "") -> str:
    if n is None:
        return "N/A"
    if n >= 1000:
        return f"{prefix}{n:,.2f}"
    return f"{prefix}{n:.2f}"


async def generate_morning_card(
    nasdaq: MarketData,
    koru: MarketData,
    date_str: str,
    chart_b64: str = "",
) -> bytes | None:
    """모닝브리핑 카드 이미지 생성, PNG bytes 반환"""

    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    template = env.get_template("daily_card.html")

    nasdaq_pct = nasdaq.change_pct or 0
    koru_pct = koru.change_pct or 0

    html = template.render(
        date_str=date_str,
        nasdaq_price=_fmt_price(nasdaq.close),
        nasdaq_pct=nasdaq_pct,
        koru_price=_fmt_price(koru.close, "$"),
        koru_pct=koru_pct,
        chart_b64=chart_b64,
    )

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(
                viewport={"width": 800, "height": 600},
                device_scale_factor=2,
            )
            await page.set_content(html, wait_until="networkidle")
            await page.wait_for_timeout(500)

            card_height = await page.evaluate("""
                () => {
                    const wrapper = document.getElementById('card-wrapper');
                    const body = document.body;
                    const bodyStyle = getComputedStyle(body);
                    const padTop = parseFloat(bodyStyle.paddingTop);
                    const padBot = parseFloat(bodyStyle.paddingBottom);
                    return wrapper.getBoundingClientRect().height + padTop + padBot;
                }
            """)
            card_height = int(card_height) + 2
            await page.set_viewport_size({"width": 800, "height": card_height})
            image_bytes = await page.screenshot(
                type="png",
                clip={"x": 0, "y": 0, "width": 800, "height": card_height},
            )
            await browser.close()

        logger.info(f"데이터 카드 이미지 생성 완료 ({len(image_bytes):,} bytes)")
        return image_bytes

    except Exception as e:
        logger.error(f"이미지 생성 실패: {e}")
        return None
