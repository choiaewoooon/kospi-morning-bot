# kospi-morning-bot

KOSPI 아침 브리핑 텔레그램 봇. **Canton과 무관** — Ozzycanton 폴더에 우연히 거주.

## 무엇을 하나

- **매일 08:40 KST**: 나스닥/$KORU/$EWY + 밤사이 뉴스(전날 18시~) 요약을 텔레그램 채널에 발송. 코스피 방향 예측 포함.
- **매일 15:45 KST**: 코스피 종가를 수집해 아침 예측을 검증, 적중률을 `predictions.db`(SQLite)에 누적.

## 운영 (launchd)

- LaunchAgent: `~/Library/LaunchAgents/com.cobling.kospi-morning-bot.plist`
  (venv 파이썬으로 `bot.py` 상주 실행, KeepAlive)
- 재기동: `launchctl kickstart -k gui/$(id -u)/com.cobling.kospi-morning-bot`
- 로그: `bot.log`(앱 로그), `launchd_stdout.log`/`launchd_stderr.log`
- 수동 실행: `venv/bin/python bot.py --now`(즉시 발송 테스트), `--verify`(즉시 검증)
- 스케줄 변경: `.env`의 `SCHEDULE_HOUR`/`SCHEDULE_MINUTE` (기본 8:40)

## 구조

| 파일 | 역할 |
|---|---|
| `bot.py` | 엔트리포인트. APScheduler cron 2개(브리핑/검증) |
| `collectors/` | Nasdaq·KORU·EWY·News 수집기 (yfinance 등) |
| `formatter.py` / `image_generator.py` / `chart_generator.py` | 리포트 텍스트·카드 이미지·차트 생성 |
| `news_summarizer.py` | 뉴스 LLM 요약 |
| `prediction_parser.py` + `db.py` | 예측 방향 파싱 + `predictions.db` 적중률 기록 |
| `config.py` | 설정 (시크릿은 `.env`, git 미추적) |

## 규칙

- 주말은 스킵한다 (코드에 반영됨, 2026-04-02).
- `predictions.db`는 적중률 히스토리 원본 — 삭제·리셋 금지.
- 코드 수정 후엔 반드시 launchd 재기동(위 kickstart)을 해야 반영된다 — 상주 프로세스라 파일만 바꾸면 옛 코드가 계속 돈다.
- 운영 중 변경은 그날 안에 커밋한다 (canton-telegram-bot에서 49일 미커밋 방치 전례 있음).
