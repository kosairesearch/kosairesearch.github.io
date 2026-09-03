#!/usr/bin/env python3
"""업종 분석 파이프라인 검사 — 돈이 나가는 자리와 화면 안내가 어긋나지 않는지.

왜 필요한가. 이 파이프라인은 분기에 한 번만 돌아서, 무엇이 어긋나도 다음
분기까지 아무도 모른다. 실제로 이런 일들이 있었다.

  · 7·8월 예정 실행이 '성공' 으로 끝났는데 본문은 한 글자도 안 바뀌었다
    (SECTOR_FORCE 가 없어 대상 0개로 조용히 끝났다)
  · 8월 6일 본문이 8월 14일 반기보고서를 못 본 채 걸려 있었다
    (크론이 실적 시즌 직전이었다)
  · 화면 위 지표는 '12개 종목' 인데 본문은 '13개 종목' 이라고 했다
    (매 거래일 바뀌는 집계 수치를 본문에 박아 뒀다)

    python3 scripts/check_sectors.py
"""
import io
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WF = ROOT / ".github" / "workflows" / "generate_sectors.yml"
GEN = ROOT / "scripts" / "generate_sectors.py"
DATA = ROOT / "data" / "sectors.js"

ok, fail = [], []


def check(cond, msg, detail=""):
    (ok if cond else fail).append(f"{msg}{(' — ' + detail) if detail else ''}")


wf = WF.read_text(encoding="utf-8")
gen = GEN.read_text(encoding="utf-8")

# ── 1) Batch API 만 쓰는가 ───────────────────────────────────
#
#    같은 모델·같은 프롬프트라도 Batch 는 요금이 절반이다. 즉시 호출로
#    새 나가면 두 배를 물지만 화면은 멀쩡해서 아무도 모른다.
check("messages.batches.create" in gen, "제출이 Batch 창구로 나간다")
# client() 가 막아 놓는 줄과, 막힌 것을 알리는 예외 이름
check("cl.messages.create = _blocked" in gen, "즉시 호출 창구(messages.create)를 막아 둔다")
check("cl.messages.stream = _blocked" in gen, "즉시 호출 창구(messages.stream)를 막아 둔다")
check("class BatchOnly" in gen, "막혔을 때 그 자리에서 멈춘다(BatchOnly)")
# 막아 두는 줄 말고 실제로 부르는 곳이 있으면 안 된다
calls = [m.start() for m in re.finditer(r"(?<!= _blocked\n)\bcl\.messages\.create\s*\(", gen)]
check(not calls, "즉시 호출을 실제로 부르는 곳이 없다", f"{len(calls)}곳")

# ── 2) 예정 실행이 전 업종을 다시 쓰는가 ──────────────────────
#
#    이게 없으면 '이미 있는 업종은 건너뛴다' 는 조건에 걸려 대상 0개로
#    조용히 성공한다. 7·8월에 실제로 두 번 그렇게 지나갔다.
check("SECTOR_FORCE" in wf, "워크플로가 SECTOR_FORCE 를 넘긴다")
check("github.event_name == 'schedule'" in wf, "예정 실행은 항상 전 업종 재생성")

# ── 3) 크론이 정기보고서 뒤에 오는가 ─────────────────────────
#
#    업종 분석에 새로 들어갈 사실은 공시로만 들어온다. 공시 전에 돌리면
#    새 숫자를 못 본 글을 다음 분기까지 걸어 둔다.
#
#      사업보고서 3/31 → 4월 · 1분기 5/15 → 6월
#      반기 8/14 → 9월 · 3분기 11/14 → 12월
crons = re.findall(r"-\s*cron:\s*'([^']+)'", wf)
check(len(crons) == 1, "크론이 하나다", f"{len(crons)}개")
if crons:
    parts = crons[0].split()
    check(len(parts) == 5, "크론이 5칸이다", crons[0])
    if len(parts) == 5:
        mi, ho, dom, mon, dow = parts
        months = sorted(int(x) for x in mon.split(",") if x.isdigit())
        check(months == [4, 6, 9, 12], "공시가 끝난 달에 돈다(4·6·9·12월)", str(months))
        # UTC 15시 이후로 잡으면 한국 날짜가 하루 밀린다
        check(ho.isdigit() and 0 <= int(ho) <= 14,
              "UTC 시각이 한국 날짜를 밀지 않는다(0~14시)", f"{ho}시")
        check(dom.isdigit() and 1 <= int(dom) <= 28,
              "실행일이 모든 달에 있는 날짜다", f"{dom}일")

# ── 4) 화면 안내가 실제 일정과 같은가 ────────────────────────
#
#    표에 적힌 날짜와 크론이 어긋나면 사이트가 거짓말을 한다. 코드를
#    고치고 안내를 잊는 쪽으로 어긋나므로, 코드에서 날짜를 읽어 맞춰 본다.
if crons and len(crons[0].split()) == 5:
    dom = crons[0].split()[2]
    months = [int(x) for x in crons[0].split()[3].split(",") if x.isdigit()]
    want = "·".join(str(m) for m in sorted(months)) + f"월 {dom}일"
    for p in ("About.html", "staging/About.html"):
        t = (ROOT / p).read_text(encoding="utf-8")
        row = re.search(r"<tr><td><b>업종 분석</b>.*?</tr>", t, re.S)
        check(bool(row), f"{p} 에 업종 분석 줄이 있다")
        if row:
            check(want in row.group(0),
                  f"{p} 의 안내 날짜가 크론과 같다({want})",
                  re.sub(r"<[^>]+>", " ", row.group(0))[:70])

# 두 파일의 업종 분석 줄은 한 글자까지 같아야 한다. 같은 표가 두 말을 하면
# 미리보기에서 본 것과 올라간 것이 달라진다(실제로 비고가 서로 달랐다).
rows = []
for p in ("About.html", "staging/About.html"):
    m = re.search(r"<tr><td><b>업종 분석</b>.*?</tr>", (ROOT / p).read_text(encoding="utf-8"), re.S)
    rows.append(m.group(0) if m else None)
check(rows[0] and rows[0] == rows[1], "실사이트와 스테이징의 안내가 같다")

# ── 5) 본문에 '매 거래일 바뀌는 숫자' 가 박히지 않았는가 ──────
#
#    화면은 본문 위에서 시가총액 합계·시장 비중·종목 수를 매 거래일 다시
#    계산해 보여 준다. 그 값이 문장에도 박혀 있으면 그날부터 위아래가
#    다른 숫자를 말한다.
check("live_number_hits" in gen, "회수할 때 집계 수치가 박혔는지 본다")
check('"agg": agg' in gen or '"agg": agg,' in gen or '"agg"' in gen,
      "제출 시점 집계를 적어 둔다(회수할 때 그 값으로 비교)")

# ── 6) 업종마다 작성 시점이 찍혀 있는가 ──────────────────────
#
#    일부 업종만 다시 쓰면 전체 lastUpdated 만으로는 어느 업종이 언제
#    쓰인 글인지 알 수 없다.
raw = DATA.read_text(encoding="utf-8")
secs = json.loads(raw[raw.index("{"):].rstrip().rstrip(";"))["sectors"]
miss = [k for k, v in secs.items() if not (v or {}).get("generatedAt")]
check(not miss, f"업종 {len(secs)}개 전부 작성 시점이 있다", ",".join(miss[:5]))
check("rep[\"generatedAt\"] = as_of" in gen, "새로 만들 때 작성 시점을 찍는다")

# ── 7) 사용량이 기록되는가 ───────────────────────────────────
#
#    이게 없어서 "월 1회로 늘리면 얼마 더 드나" 를 기록으로 답할 수 없었다.
check("_tally" in gen and "_log_usage" in gen, "쓴 토큰과 웹 검색 횟수를 로그에 남긴다")

print(f"통과 {len(ok)} · 실패 {len(fail)}\n")
for m in ok:
    print("  PASS", m)
for m in fail:
    print("  FAIL", m)
sys.exit(1 if fail else 0)
