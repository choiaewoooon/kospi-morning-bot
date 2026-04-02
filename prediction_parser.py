"""
Claude 코멘트에서 예측 방향 파싱
"""
import re


def parse_direction(comment: str) -> str:
    """코멘트에서 코스피 예측 방향 추출 (up/down/neutral)"""
    if not comment:
        return "neutral"

    text = comment.lower()

    up_keywords = [
        "갭업", "상승", "오를", "올라", "오르", "올랐", "따라갈",
        "긍정", "호재", "반등", "강세", "출발", "좋",
        "up", "bull", "green",
    ]
    down_keywords = [
        "갭다운", "하락", "떨어", "내려", "내릴", "빠질", "빠지",
        "부정", "악재", "약세", "조정", "눌림",
        "down", "bear", "red",
    ]

    up_count = sum(1 for kw in up_keywords if kw in text)
    down_count = sum(1 for kw in down_keywords if kw in text)

    if up_count > down_count:
        return "up"
    elif down_count > up_count:
        return "down"
    return "neutral"
