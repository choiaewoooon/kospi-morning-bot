"""
나스닥 + KORU 차트 이미지 생성 (matplotlib)
tree.news 스타일 다크 테마 캔들차트
"""
import base64
import logging
from io import BytesIO

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

from collectors import MarketData

logger = logging.getLogger(__name__)

# 색상 팔레트
BG_COLOR = "#0a0e17"
CARD_BG = "#0f1923"
GRID_COLOR = "#1c2636"
TEXT_COLOR = "#d1d4dc"
TEXT_DIM = "#636e7e"
UP_COLOR = "#26a69a"
DOWN_COLOR = "#ef5350"
VOLUME_UP = "#1a3a35"
VOLUME_DOWN = "#3a1a1a"


def _draw_candles(ax, ohlc_data: list, show_volume: bool = True):
    """캔들차트 + 볼륨 바"""
    if not ohlc_data:
        ax.text(0.5, 0.5, "No Data", ha="center", va="center",
                transform=ax.transAxes, color=TEXT_DIM, fontsize=14)
        return

    n = len(ohlc_data)
    prices_high = []
    prices_low = []

    for i, c in enumerate(ohlc_data):
        o, h, l, cl = c["open"], c["high"], c["low"], c["close"]
        is_up = cl >= o
        color = UP_COLOR if is_up else DOWN_COLOR

        # 꼬리 (위크)
        ax.plot([i, i], [l, h], color=color, linewidth=0.8, solid_capstyle="round")
        # 몸통
        body_bottom = min(o, cl)
        body_height = abs(cl - o) or (h - l) * 0.01
        ax.bar(i, body_height, bottom=body_bottom, width=0.6,
               color=color, edgecolor=color, linewidth=0)

        prices_high.append(h)
        prices_low.append(l)

    # Y축 범위 여유
    price_min = min(prices_low)
    price_max = max(prices_high)
    price_range = price_max - price_min
    ax.set_ylim(price_min - price_range * 0.05, price_max + price_range * 0.08)
    ax.set_xlim(-1, n + 0.5)

    # 마지막 가격에 수평 점선 + 라벨
    last = ohlc_data[-1]
    last_close = last["close"]
    last_color = UP_COLOR if last["close"] >= last["open"] else DOWN_COLOR
    ax.axhline(y=last_close, color=last_color, linewidth=0.6, linestyle="--", alpha=0.5)

    # 오른쪽에 현재가 라벨
    ax.annotate(
        f" {last_close:,.2f}",
        xy=(n - 0.5, last_close),
        fontsize=8,
        fontweight="bold",
        color="#fff",
        backgroundcolor=last_color,
        bbox=dict(boxstyle="round,pad=0.2", facecolor=last_color, edgecolor=last_color, alpha=0.9),
        va="center",
    )

    # 스타일링
    ax.set_facecolor(CARD_BG)
    ax.tick_params(axis="x", colors=TEXT_DIM, labelsize=7)
    ax.tick_params(axis="y", colors=TEXT_DIM, labelsize=8)
    ax.yaxis.tick_right()
    ax.yaxis.set_label_position("right")
    ax.set_xticks([])
    ax.grid(True, axis="y", color=GRID_COLOR, linewidth=0.5)
    ax.spines["top"].set_visible(False)
    ax.spines["bottom"].set_color(GRID_COLOR)
    ax.spines["left"].set_visible(False)
    ax.spines["right"].set_color(GRID_COLOR)

    # 천 단위 콤마
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:,.2f}"))


def _draw_volume(ax, ohlc_data: list):
    """볼륨 바 (하단)"""
    if not ohlc_data:
        return

    n = len(ohlc_data)
    for i, c in enumerate(ohlc_data):
        vol = c.get("volume", 0) or 0
        is_up = c["close"] >= c["open"]
        color = UP_COLOR if is_up else DOWN_COLOR
        alpha = 0.4
        ax.bar(i, vol, width=0.6, color=color, alpha=alpha, linewidth=0)

    ax.set_xlim(-1, n + 0.5)
    ax.set_facecolor(CARD_BG)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.spines["top"].set_visible(False)
    ax.spines["bottom"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.spines["right"].set_visible(False)


async def generate_charts_base64(nasdaq: MarketData, koru: MarketData) -> str:
    """나스닥 + KORU 차트를 생성하여 base64 반환"""

    try:
        fig = plt.figure(figsize=(8, 6), facecolor=BG_COLOR)

        # 2행: 나스닥(위) + KORU(아래), 각각 캔들+볼륨
        gs = fig.add_gridspec(
            4, 1,
            height_ratios=[3, 1, 3, 1],
            hspace=0.08,
        )

        ax_nasdaq = fig.add_subplot(gs[0])
        ax_nasdaq_vol = fig.add_subplot(gs[1], sharex=ax_nasdaq)
        ax_koru = fig.add_subplot(gs[2])
        ax_koru_vol = fig.add_subplot(gs[3], sharex=ax_koru)

        # 나스닥 타이틀
        nasdaq_title = "NASDAQ Composite"
        if nasdaq.close and nasdaq.change_pct is not None:
            arrow = "+" if nasdaq.change_pct >= 0 else ""
            color = UP_COLOR if nasdaq.change_pct >= 0 else DOWN_COLOR
            ax_nasdaq.text(
                0.01, 1.05, nasdaq_title, transform=ax_nasdaq.transAxes,
                fontsize=11, fontweight="bold", color=TEXT_COLOR, va="bottom",
            )
            ax_nasdaq.text(
                0.35, 1.05, f"{nasdaq.close:,.2f}  {arrow}{nasdaq.change_pct:.2f}%",
                transform=ax_nasdaq.transAxes,
                fontsize=11, fontweight="bold", color=color, va="bottom",
            )
        else:
            ax_nasdaq.set_title(nasdaq_title, loc="left", fontsize=11,
                               fontweight="bold", color=TEXT_COLOR)

        # 나스닥 차트
        _draw_candles(ax_nasdaq, nasdaq.ohlc_data)
        _draw_volume(ax_nasdaq_vol, nasdaq.ohlc_data)

        # KORU 타이틀
        koru_title = "$KORU (Korea Bull 3X)"
        if koru.close and koru.change_pct is not None:
            arrow = "+" if koru.change_pct >= 0 else ""
            color = UP_COLOR if koru.change_pct >= 0 else DOWN_COLOR
            ax_koru.text(
                0.01, 1.05, koru_title, transform=ax_koru.transAxes,
                fontsize=11, fontweight="bold", color=TEXT_COLOR, va="bottom",
            )
            ax_koru.text(
                0.42, 1.05, f"${koru.close:,.2f}  {arrow}{koru.change_pct:.2f}%",
                transform=ax_koru.transAxes,
                fontsize=11, fontweight="bold", color=color, va="bottom",
            )
        else:
            ax_koru.set_title(koru_title, loc="left", fontsize=11,
                              fontweight="bold", color=TEXT_COLOR)

        # KORU 차트
        _draw_candles(ax_koru, koru.ohlc_data)
        _draw_volume(ax_koru_vol, koru.ohlc_data)

        buf = BytesIO()
        fig.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                    pad_inches=0.3, facecolor=BG_COLOR)
        plt.close(fig)
        buf.seek(0)

        b64 = base64.b64encode(buf.read()).decode("utf-8")
        logger.info("차트 이미지 생성 완료")
        return b64

    except Exception as e:
        logger.error(f"차트 생성 실패: {e}")
        return ""
