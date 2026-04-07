"""
예측 기록 DB (SQLite)
"""
import aiosqlite
import logging
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent / "predictions.db"

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT UNIQUE NOT NULL,
    nasdaq_pct REAL,
    koru_pct REAL,
    ewy_pct REAL,
    predicted_direction TEXT,
    prediction_comment TEXT,
    kospi_open REAL,
    kospi_close REAL,
    kospi_pct REAL,
    actual_direction TEXT,
    correct INTEGER,
    miss_reason TEXT
)
"""


async def init_db():
    """DB 초기화"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(CREATE_TABLE)
        await db.commit()
    logger.info("DB 초기화 완료")


async def save_prediction(
    dt: date,
    nasdaq_pct: float | None,
    koru_pct: float | None,
    ewy_pct: float | None,
    predicted_direction: str,
    prediction_comment: str,
):
    """아침 예측 저장"""
    async with aiosqlite.connect(DB_PATH) as db:
        # 이미 검증된 레코드가 있으면 예측 부분만 업데이트 (검증 결과 보존)
        await db.execute(
            """
            INSERT INTO predictions
            (date, nasdaq_pct, koru_pct, ewy_pct, predicted_direction, prediction_comment)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
                nasdaq_pct = excluded.nasdaq_pct,
                koru_pct = excluded.koru_pct,
                ewy_pct = excluded.ewy_pct,
                predicted_direction = excluded.predicted_direction,
                prediction_comment = excluded.prediction_comment
            """,
            (dt.isoformat(), nasdaq_pct, koru_pct, ewy_pct,
             predicted_direction, prediction_comment),
        )
        await db.commit()
    logger.info(f"예측 저장: {dt} → {predicted_direction}")


async def update_actual(
    dt: date,
    kospi_open: float,
    kospi_close: float,
    kospi_pct: float,
    actual_direction: str,
    correct: bool,
    miss_reason: str = "",
):
    """오후 실제 결과 업데이트"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            UPDATE predictions
            SET kospi_open = ?, kospi_close = ?, kospi_pct = ?,
                actual_direction = ?, correct = ?, miss_reason = ?
            WHERE date = ?
            """,
            (kospi_open, kospi_close, kospi_pct,
             actual_direction, int(correct), miss_reason, dt.isoformat()),
        )
        await db.commit()
    logger.info(f"실제 결과 업데이트: {dt} → {actual_direction} (적중: {correct})")


async def get_prediction(dt: date) -> dict | None:
    """특정 날짜의 예측 기록 조회"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM predictions WHERE date = ?",
            (dt.isoformat(),),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_recent_records(days: int = 14) -> list[dict]:
    """최근 N일 검증 완료된 기록 조회"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT * FROM predictions
            WHERE actual_direction IS NOT NULL
            ORDER BY date DESC
            LIMIT ?
            """,
            (days,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_accuracy(days: int = 14) -> dict:
    """최근 적중률 통계"""
    records = await get_recent_records(days)
    if not records:
        return {"total": 0, "correct": 0, "rate": 0.0, "records": []}

    total = len(records)
    correct = sum(1 for r in records if r["correct"])
    return {
        "total": total,
        "correct": correct,
        "rate": correct / total * 100 if total > 0 else 0.0,
        "records": records,
    }
