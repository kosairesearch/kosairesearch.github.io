#!/usr/bin/env python3
"""모델마다 다른 요청 설정 — 사고(thinking)를 끄는 법 (2026-10-27 · 소넷을 Sonnet 5.5 로 옮기며).

사고가 필요 없는 호출(브리핑 수리 · 업종 분류)은 사고를 꺼서 부른다. 끄는 법이 모델마다 다르다.
  · Sonnet 5.5 — {"type": "disabled"} 를 400 으로 거절한다. 가장 낮은 단계는 {"type": "between_tools"} 다
    (확장 사고 없음 — 도구를 부르는 사이의 짧은 진행 메모만 thinking 블록으로 온다). 사고 깊이 high 이하에서만
    받고, thinking 안에 다른 칸을 넣으면 400 이다. 다른 모델은 모두 between_tools 를 거절한다.
  · Sonnet 5 · Opus 5 · Haiku 5.5 — {"type": "disabled"}(사고 깊이 high 이하).
  · 4.x 모델 — thinking 을 비워 두면 꺼진다.
Sonnet 5 이후 모델은 thinking 을 비워 두면 사고가 *켜진다*. 사고 토큰도 출력 한도(max_tokens) 안에서 세므로,
비워 둔 분류 호출은 사고가 한도를 먹어 답이 잘린다 — 모델을 바꿀 때 이 표부터 본다.
Opus 5.5 는 사고를 끌 수 없다(사고 깊이만 조절한다) — 이런 호출에 쓰지 않는다.
지키는 검사 scripts/test_brief_gen.py · scripts/tests/batch_only_test.py.
"""

_BETWEEN_TOOLS = {"claude-sonnet-5-5"}
_DISABLED = {"claude-sonnet-5", "claude-opus-5", "claude-haiku-5-5"}


def thinking_off(model):
    """요청에 펼쳐 넣을 thinking 설정({**thinking_off(model)}) — 그 모델이 받는 '사고 끔'. 4.x 모델은 빈 dict."""
    if model in _BETWEEN_TOOLS:
        return {"thinking": {"type": "between_tools"}}
    if model in _DISABLED:
        return {"thinking": {"type": "disabled"}}
    return {}
