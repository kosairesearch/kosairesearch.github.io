"""서술형 설명 생성 — Claude + web search.

모델은 '문장'만 쓴다(회사 정의/사업/최근 사건/리스크). 숫자 지표는 compose가
코드로 채운다. DART 최근 공시를 근거로 넘겨 시점 앵커링을 강제한다.
반환: {"definition","business","recent","risks"} (target 언어).
env: ANTHROPIC_API_KEY, NEWS_MODEL(기본 claude-sonnet-4-6), WEB_SEARCH_MAX(기본 5)
"""
import json
import os
import re

MODEL = os.environ.get("NEWS_MODEL", "claude-sonnet-4-6")
WEB_SEARCH_MAX = int(os.environ.get("WEB_SEARCH_MAX", "5"))

_RULES_KO = (
    "너는 한국 주식을 설명하는 리서치 봇이다. 아래 회사를 한국어로 사실 기반으로 설명한다.\n"
    "원칙(엄격):\n"
    "- 매수/매도/목표가/'싸다·비싸다·오를것' 등 투자 권유·방향성 표현 절대 금지. 사실만 서술.\n"
    "- 비유·수사 금지. 어려운 용어는 괄호 안에 한 줄로 풀어라. 예: 파운드리(반도체 위탁생산).\n"
    "- 사건성 내용은 반드시 시점을 앵커링하라. 예: '올해 1월', '2024년 하반기'. 모르면 쓰지 마라.\n"
    "- 최신 사실은 web search로 확인하라. 추측·불확실한 수치는 쓰지 마라(숫자 지표는 코드가 따로 채운다).\n"
    "- 규모가 작은 종목은 억지로 늘리지 말고 아는 만큼만 간결하게.\n"
    "각 섹션을 JSON으로만 반환:\n"
    '{"definition":"이 회사가 무엇을 하는 회사인지 2~3문장. 핵심 정의가 맨 앞에 오게.",'
    '"business":"무엇으로 돈을 버는지(사업/수익구조) 2~4문장.",'
    '"recent":"최근 상황·핵심 사건 2~4문장(시점 앵커링 필수). 특이사항 없으면 빈 문자열.",'
    '"risks":"참고할 리스크 1~3문장(중립적 사실). 없으면 빈 문자열."}'
)
_RULES_EN = (
    "You are a research bot explaining Korean stocks. Explain the company below in English, "
    "factually.\nRules (strict):\n"
    "- Never give buy/sell/price-target or any directional view ('cheap/expensive/will rise'). Facts only.\n"
    "- No metaphors. Explain jargon in a short parenthetical, e.g. foundry (contract chip manufacturing).\n"
    "- Anchor any event in time, e.g. 'in January this year', 'in H2 2024'. If unknown, omit it.\n"
    "- Verify recent facts with web search. No speculation or uncertain figures (numeric metrics are "
    "filled separately by code).\n"
    "- For small companies, keep it short; don't pad.\n"
    "Return JSON only:\n"
    '{"definition":"2-3 sentences on what the company does; lead with the core definition.",'
    '"business":"2-4 sentences on how it makes money.",'
    '"recent":"2-4 sentences on recent situation/key events (must be time-anchored). Empty string if none.",'
    '"risks":"1-3 sentences of neutral risk factors. Empty string if none."}'
)


def generate(stock, disclosures, lang):
    """stock: {name,name_en,ticker,sector,market}, disclosures: [{title,date}], lang: 'ko'|'en'."""
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    name = stock.get("name") if lang == "ko" else (stock.get("name_en") or stock.get("name"))
    rules = _RULES_KO if lang == "ko" else _RULES_EN
    if WEB_SEARCH_MAX <= 0:   # 웹서치 꺼짐 — 공시·확실한 지식만, 불확실하면 생략
        rules += ("\n(웹검색 없음: 제공된 공시 목록과 확실히 아는 사실만 사용하고, "
                  "불확실한 내용은 쓰지 말고 생략하라.)" if lang == "ko" else
                  "\n(No web search available: use only the provided filings and facts "
                  "you are certain of; omit anything uncertain.)")
    disc = "\n".join(f"- {d['date']}: {d['title']}" for d in (disclosures or [])[:8])
    ctx = (
        f"회사: {stock.get('name')} ({stock.get('name_en') or ''}) / 코드 {stock.get('ticker')}\n"
        f"시장: {stock.get('market')} / 섹터: {stock.get('sector')}\n"
        + (f"최근 DART 공시(근거·시점앵커용):\n{disc}\n" if disc else "")
    )
    kwargs = dict(
        model=MODEL,
        max_tokens=3000,
        system=rules,
        messages=[{"role": "user", "content":
                   ctx + f"\n위 회사를 설명해줘. ({'한국어' if lang == 'ko' else 'English'})"}],
    )
    # WEB_SEARCH_MAX=0 이면 웹서치 완전 비활성(비용 절감 모드) — 최근 사건 근거는 DART 공시만
    if WEB_SEARCH_MAX > 0:
        kwargs["tools"] = [{"type": "web_search_20250305", "name": "web_search",
                            "max_uses": WEB_SEARCH_MAX}]
    msg = client.messages.create(**kwargs)
    txt = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    m = re.search(r"\{.*\}", txt, re.S)
    if not m:
        return None
    try:
        from json_repair import repair_json
        return json.loads(repair_json(m.group(0)))
    except Exception:
        try:
            return json.loads(m.group(0))
        except Exception:
            return None
