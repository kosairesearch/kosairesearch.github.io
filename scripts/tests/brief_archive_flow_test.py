#!/usr/bin/env python3
"""모닝브리핑 지난 호 — 아침 발행 흐름 회귀 검사(2026-10-04). 돈 드는 호출 없이 브리핑 자료의 사본(임시 폴더)에서 돌린다.

  python3 scripts/tests/brief_archive_flow_test.py

아침 작업 ④ 의 render_brief.py 가 하는 일을 그대로 밟는다 — 발행 시각과 함께 호수(meta.issueNo)를 적고, brief.html 에 호수 ·
이전 호 · 지난 호 목록을 붙이고, 실사이트 지난 호(그날 호의 고정 페이지 · 전날 호의 '다음 호' · 목록)를 만든다.

무엇을 고정해 두나
  ① 새 호 발행     다음 거래일 원고를 발행하면 제32호가 적히고, brief.html · 그날 고정 페이지가 제32호다. 전날 호(제31호)에 '다음 호'가
                   붙고 대표 주소(canonical)가 자기 주소로 바뀐다. 새 호의 고정 페이지는 brief.html 을 대표로 가리킨다. 목록은 32편.
  ② 같은 글       render_brief 가 쓴 brief.html = 실사이트 생성기(build_live)가 같은 자료로 그린 brief.html — 글자 하나까지.
  ③ 호수 고정     지난 호 하나의 발행 기록을 지워도 뒤 호수가 밀리지 않는다(적힌 호수를 쓴다). 랜딩 '제N호 읽기'도 같은 수.
  ④ 다시 그리기   이미 발행한 호를 다시 그려도 호수 · 발행 시각이 그대로다.
  ⑤ 발행을 막지 않음  지난 호 연결이나 지난 호 페이지 만들기가 멈춰도 brief.html 과 발행 기록은 쓰이고 0 으로 끝난다.
"""
import io
import json
import re
import shutil
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE.parent))

import render_brief as RB          # noqa: E402
import build_brief_comp as BB      # noqa: E402
import stamp_counts as SC          # noqa: E402

passed = failed = 0


def ok(cond, what, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ✔ {what}{(' — ' + detail) if detail else ''}")
    else:
        failed += 1
        print(f"  ✘ {what}{(' — ' + detail) if detail else ''}")


SRC = ROOT / "data" / "briefs"
LAST = sorted(p.stem for p in SRC.glob("*.json") if re.fullmatch(r"\d{4}-\d\d-\d\d", p.stem)
              and (json.loads(p.read_text(encoding="utf-8")).get("meta") or {}).get("publishedAt"))[-1]
NEW = "2099-01-02"   # 앞으로 올 거래일 — 실제 자료와 겹치지 않는 날


def sandbox():
    """브리핑 자료 사본 · 빈 실사이트 폴더. render_brief · build_brief_comp · stamp_counts 가 그쪽을 보게 한다."""
    t = Path(tempfile.mkdtemp())
    (t / "briefs").mkdir()
    for f in SRC.glob("*.json"):
        shutil.copy(f, t / "briefs" / f.name)
    (t / "site").mkdir()
    RB.BRIEFS, RB.PAGE, SC.BRIEFS = t / "briefs", t / "site" / "brief.html", t / "briefs"
    return t


def draft(t, date, title="시험용 새 호 제목", title_en="Test issue headline"):
    """발행하지 않은 원고 하나(가장 최근 호의 사본 · 발행 기록과 호수 없음)."""
    doc = json.loads((t / "briefs" / f"{LAST}.json").read_text(encoding="utf-8"))
    doc["date"] = date
    doc["title"] = {"ko": title, "en": title_en}
    doc["meta"] = {k: v for k, v in doc["meta"].items() if k not in ("publishedAt", "issueNo")}
    (t / "briefs" / f"{date}.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")


def publish(date, at="07:28"):
    buf = io.StringIO()
    old = sys.argv
    sys.argv = ["render_brief.py", "--date", date, "--at", at]
    try:
        with redirect_stdout(buf), redirect_stderr(buf):   # render_brief 의 기록(log)은 stderr 로 나간다
            code = RB.main()
    finally:
        sys.argv = old
    return code, buf.getvalue()


def meta(t, date):
    return json.loads((t / "briefs" / f"{date}.json").read_text(encoding="utf-8")).get("meta") or {}


def canon(html):
    m = re.search(r'<link rel="canonical" href="([^"]+)"', html)
    return m.group(1) if m else None


def no_of(html):
    m = re.search(r'<div class="mb-date" data-no="제(\d+)호" data-n="(\d+)">', html)
    return int(m.group(1)) if m and m.group(1) == m.group(2) else None


def build_live_brief(t):
    """실사이트 생성기(build_live 의 build_pages 와 같은 함수)가 같은 자료로 그린 brief.html."""
    (t / "live").mkdir(exist_ok=True)
    out = t / "live" / "brief.html"   # 파일 이름이 검색 노출 머리(LIVE_SEO)의 열쇠다
    BB.C.set_mode("live")
    with redirect_stdout(io.StringIO()):
        BB.build(None, str(out))
    return out.read_text(encoding="utf-8")


real = (RB.BRIEFS, RB.PAGE, SC.BRIEFS)
try:
    n_pub = len([p for p in SRC.glob("*.json") if re.fullmatch(r"\d{4}-\d\d-\d\d", p.stem)
                 and (json.loads(p.read_text(encoding="utf-8")).get("meta") or {}).get("publishedAt")])
    want = n_pub + 1
    print(f"── 지금 발행한 브리핑 {n_pub}편(마지막 {LAST}) · 새 호 {NEW} → 제{want}호")

    # ① 새 호 발행 · ② 같은 글
    t = sandbox()
    draft(t, NEW)
    code, out = publish(NEW)
    site = t / "site"
    m = meta(t, NEW)
    ok(code == 0 and m.get("issueNo") == want and str(m.get("publishedAt", ""))[11:16] == "07:28",
       f"① 새 호를 발행하면 발행 시각과 함께 제{want}호가 적힌다", f"종료 {code} · 호수 {m.get('issueNo')} · 발행 {m.get('publishedAt')}")
    brief = (site / "brief.html").read_text(encoding="utf-8")
    new_page = (site / BB.issue_file(NEW)).read_text(encoding="utf-8") if (site / BB.issue_file(NEW)).exists() else ""
    prev_page = (site / BB.issue_file(LAST)).read_text(encoding="utf-8") if (site / BB.issue_file(LAST)).exists() else ""
    arch = (site / BB.ARCHIVE).read_text(encoding="utf-8") if (site / BB.ARCHIVE).exists() else ""
    ok(no_of(brief) == want and f'href="{BB.issue_file(LAST)}"' in brief and 'class="mb-old"' not in brief
       and f'href="{BB.ARCHIVE}"' in brief and canon(brief) == "https://kosai.kr/brief.html",
       f"① brief.html — 제{want}호 · 이전 호({LAST}) · 지난 호 목록 연결 · 대표 주소는 자기 주소")
    ok(no_of(new_page) == want and canon(new_page) == "https://kosai.kr/brief.html" and 'class="mb-nv mb-nv--next"' not in new_page,
       f"① 새 호의 고정 페이지 — 제{want}호 · 대표 주소는 brief.html(같은 글) · 다음 호 없음", canon(new_page) or "없음")
    ok(no_of(prev_page) == want - 1 and canon(prev_page) == f"https://kosai.kr/{BB.issue_file(LAST)}"
       and f'class="mb-nv mb-nv--next" href="{BB.issue_file(NEW)}"' in prev_page and "시험용 새 호 제목" in prev_page
       and 'class="mb-old"' in prev_page,
       f"① 전날 호(제{want - 1}호) — '다음 호'가 새 호를 가리키고 지난 호 알림이 붙고 대표 주소가 자기 주소로", canon(prev_page) or "없음")
    rows = re.findall(r'<li><a href="(brief-[\d-]+\.html)"><span class="ba-no">제(\d+)호</span>', arch)
    ok(len(rows) == want and rows[0] == (BB.issue_file(NEW), str(want)) and f"모닝브리핑 {want}편" in arch,
       f"① 지난 호 목록 — {want}편 · 맨 위가 새 호", f"{len(rows)}줄 · 맨 위 {rows[0] if rows else '-'}")
    live = build_live_brief(t)
    ok(live == brief, "② render_brief 가 쓴 brief.html = 실사이트 생성기가 같은 자료로 그린 brief.html(글자 하나까지)",
       "" if live == brief else f"길이 {len(brief)} vs {len(live)}")
    ok(SC.brief_no() == want, f"① 랜딩 '제N호 읽기'(stamp_counts.brief_no)도 제{want}호", str(SC.brief_no()))

    # ④ 다시 그리기 — 호수 · 발행 시각 그대로
    before = meta(t, NEW)
    code2, _ = publish(NEW, at="11:05")
    after = meta(t, NEW)
    ok(code2 == 0 and after.get("issueNo") == before.get("issueNo") and after.get("publishedAt") == before.get("publishedAt"),
       "④ 이미 발행한 호를 다시 그려도 호수 · 발행 시각이 그대로", f"{before.get('issueNo')}/{before.get('publishedAt')} → {after.get('issueNo')}/{after.get('publishedAt')}")

    # ③ 호수 고정 — 가운데 호 하나의 발행 기록을 지우고 다시 만들어도 뒤 호수는 그대로
    dates = [d for d, _ in BB.published()]
    mid = dates[len(dates) // 2]
    doc = json.loads((t / "briefs" / f"{mid}.json").read_text(encoding="utf-8"))
    doc["meta"].pop("publishedAt", None)
    (t / "briefs" / f"{mid}.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    BB.C.set_mode("live")
    with redirect_stdout(io.StringIO()):
        BB.build_archive(site)
    after_mid = dates[len(dates) // 2 + 1]
    page_after = (site / BB.issue_file(after_mid)).read_text(encoding="utf-8")
    want_after = (json.loads((t / "briefs" / f"{after_mid}.json").read_text(encoding="utf-8")).get("meta") or {}).get("issueNo")
    ok(not (site / BB.issue_file(mid)).exists() and no_of(page_after) == want_after and SC.brief_no() == want,
       f"③ 지난 호 하나({mid})를 내려도 뒤 호수가 밀리지 않는다", f"{after_mid} 는 그대로 제{no_of(page_after)}호 · 랜딩 제{SC.brief_no()}호")

    # ⑤ 발행을 막지 않음 — 지난 호 페이지 만들기가 멈춰도
    t2 = sandbox()
    draft(t2, NEW)
    orig = BB.build_archive
    BB.build_archive = lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("시험 실패"))
    try:
        code3, out3 = publish(NEW)
    finally:
        BB.build_archive = orig
    m3 = meta(t2, NEW)
    ok(code3 == 0 and (t2 / "site" / "brief.html").exists() and m3.get("publishedAt") and m3.get("issueNo") == want
       and "지난 호 페이지를 만들지 못했습니다" in out3,
       "⑤ 지난 호 페이지 만들기가 멈춰도 brief.html · 발행 기록 · 호수는 쓰이고 0 으로 끝난다(경고만)", f"종료 {code3}")

    # ⑤ 지난 호 연결(이웃 호 찾기)이 멈춰도
    t3 = sandbox()
    draft(t3, NEW)
    orig_issue = RB.brief_issue
    RB.brief_issue = lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("시험 실패"))
    try:
        code4, out4 = publish(NEW)
    finally:
        RB.brief_issue = orig_issue
    b4 = (t3 / "site" / "brief.html").read_text(encoding="utf-8") if (t3 / "site" / "brief.html").exists() else ""
    m4 = meta(t3, NEW)
    ok(code4 == 0 and "시험용 새 호 제목" in b4 and m4.get("publishedAt") and "지난 호 연결을 붙이지 못했습니다" in out4,
       "⑤ 지난 호 연결이 멈춰도 이번 호만 그려 발행하고 0 으로 끝난다(경고만)", f"종료 {code4}")
finally:
    RB.BRIEFS, RB.PAGE, SC.BRIEFS = real

print(f"\n통과 {passed} · 실패 {failed}")
sys.exit(1 if failed else 0)
