# KOSPI Morning Bot

매일 아침 코스피 개장 전 브리핑을 텔레그램 채널에 자동 발송하고, 장 마감 후 실제 종가로 그날의 예측을 스스로 채점하는 Python 봇.

- **08:40 KST** — 나스닥(^IXIC)·KORU·EWY 마감 지표와 밤사이 외신 뉴스를 수집 → LLM 요약 → 다크 테마 캔들차트·모닝 카드 이미지와 함께 채널 발송
- **15:45 KST** — 코스피 종가를 수집해 아침 예측(방향)을 자동 검증하고, 결과를 SQLite에 누적

핵심은 **자가검증 루프**다. LLM이 만든 아침 브리핑의 예측을 그대로 믿고 끝내는 게 아니라, 장 마감 후 실제 종가와 대조해 정·오답을 기록하고 틀린 원인 분석까지 남긴다. LLM 출력을 "그럴듯함"이 아니라 **결과로 검증**하는 구조.

## 주요 기능

- **모닝 브리핑**: 나스닥/KORU(코리아 3x ETF)/EWY 마감 지표 + 외신 뉴스(RSS·NewsAPI) 요약
- **예측 자가검증**: 아침 예측 방향 → 종가 대조 → 정오답 기록 → 오답 원인 분석 누적 (SQLite)
- **이미지 카드**: matplotlib 캔들차트 + Jinja2 HTML 템플릿 렌더
- **무중단 스케줄**: APScheduler(코드 내장) · macOS launchd(실제 운영)

## Tech Stack

| 카테고리 | 기술 |
|---|---|
| 런타임 | Python 3.11+ · asyncio |
| 시세 | yfinance |
| 뉴스 | RSS(NYT·BBC Business) + NewsAPI/RapidAPI |
| LLM 요약·오답 분석 | Gemini CLI 래퍼 경유 (환경에 맞는 LLM CLI로 교체 가능) |
| 발송 | python-telegram-bot |
| 이미지 | matplotlib + Jinja2 |
| 저장 | SQLite (예측·검증 기록) |
| 스케줄 | APScheduler · launchd |

## 실행

```bash
pip install -r requirements.txt
cp .env.example .env   # 텔레그램 토큰·채널 ID 등 입력

python bot.py --now     # 즉시 1회 발송 (테스트)
python bot.py --verify  # 검증 1회 실행 (테스트)
python bot.py           # 스케줄러 모드 (매일 자동)
```

시크릿은 전부 `.env`로 주입한다(레포에 키 없음). 자매 프로젝트: [canton-telegram-bot](https://github.com/choiaewoooon/canton-telegram-bot) — 같은 패턴의 데일리 리포트 봇.
