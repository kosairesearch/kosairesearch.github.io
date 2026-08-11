#!/usr/bin/env python3
"""실제 사이트 배포 — 무엇을 올릴지 사람이 고르지 않는다.

왜 필요한가. 스테이징은 publish_staging.py 가 만든다. 올릴 파일이 코드에 적혀
있고, 패치 지점을 못 찾으면 빌드가 멈춘다. 그런데 실제 사이트는 손으로 복사해
왔다. 목록도 검증도 없으니 '바뀐 파일만 복사' 같은 방식이 되고, 실제로

  · 멤버십 문구를 전 페이지에 반영하면서 결제 화면이 통째로 딸려 갔고
  · 정작 그 화면들이 부르는 paywall.js·payment-config.js 는 안 가서
    실제 사이트의 결제 페이지가 '불러오는 중…'에서 멈춰 있었다

이 스크립트는 그 두 가지를 구조적으로 막는다.

  1) 올릴 파일을 사람이 고르지 않는다. 진입 페이지에서 시작해 참조를 따라가며
     필요한 파일을 전부 모은다(deps). 빠뜨릴 방법이 없다.
  2) 올리기 전에 검사한다. 하나라도 걸리면 배포하지 않는다.
     · 참조된 로컬 파일이 실제로 있는가
     · 스테이징 전용 흔적이 섞이지 않았는가(모의 백엔드·STAGING 띠·강제 잠금·noindex)
     · 아직 자리표시자인 값이 남아 있지 않은가(토스 키, 사업자 정보)
     · 유료화를 켠다면 publish_paid.py 를 돌렸는가

  python3 scripts/publish_live.py --check                 # 검사만
  python3 scripts/publish_live.py --check --paid          # 유료화 켠 상태로 검사
  python3 scripts/publish_live.py <배포대상 체크아웃 경로> # 검사 통과 시 복사
"""
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 진입 페이지. 여기서부터 참조를 따라가며 나머지를 스스로 찾는다.
ENTRIES = [
    "Home.html", "Reports.html", "industry.html", "Screener.html", "Watchlist.html",
    "stock.html", "About.html", "Contact.html", "Feedback.html",
    "Terms.html", "Privacy.html", "Login.html", "Signup.html",
    "auth-action.html", "index.html",
]

# 유료화를 켤 때 함께 올라가야 하는 진입 페이지
PAID_ENTRIES = ["pricing.html", "checkout.html", "billing.html"]

# 참조를 훑을 때 볼 것들 — HTML 속성, CSS url(), JS import/fetch
REF = re.compile(
    r"""(?:src|href)\s*=\s*["']([^"'#?]+)["']"""
    r"""|url\(\s*["']?([^"')?#]+)["']?\s*\)"""
    r"""|(?:from|import)\s*["']([^"']+)["']"""
    r"""|fetch\(\s*["'`]([^"'`?]+)""",
    re.I,
)

SKIP_PREFIX = ("http://", "https://", "//", "data:", "mailto:", "tel:", "#", "javascript:")
# 코드 조각이 경로처럼 잡히는 걸 막는다 — `${href}` 같은 템플릿, data: URI 안의
# %3C, fetch(u) 의 변수 이름 등. 실제 파일만 확장자로 걸러 낸다.
FILE_EXT = (".html", ".js", ".css", ".json", ".txt", ".xml", ".webmanifest",
            ".png", ".jpg", ".jpeg", ".svg", ".webp", ".ico", ".woff", ".woff2")

# 실제 사이트에 있으면 안 되는 흔적. 스테이징에서만 쓰는 것들이다.
FORBIDDEN = [
    ("demo-backend.js", "모의 결제 백엔드"),
    ("__KOSDEMO", "모의 결제 분기"),
    ("kos-staging-bar", "STAGING 띠"),
    ("qp('paywall')!=='0'", "강제 잠금(스테이징 전용)"),
    ('content="noindex,nofollow"', "검색 차단 메타"),
]
# 로그인해야 보는 화면은 검색에 안 걸리는 게 맞다 — noindex 검사에서 뺀다.
NOINDEX_OK = {"billing.html", "checkout.html", "auth-action.html"}

# 출시 전에 채워야 하는 자리표시자
PLACEHOLDERS = [
    ("[TOSS_CLIENT_KEY]", "토스페이먼츠 클라이언트 키"),
    ("[상호]", "사업자 상호"),
    ("[대표자명]", "대표자명"),
    ("[000-00-00000]", "사업자등록번호"),
    ("[제0000-0000-00000호]", "통신판매업 신고번호"),
    ("[사업장 주소]", "사업장 주소"),
    ("[00-0000-0000]", "대표전화"),
]


def log(m):
    print(m, flush=True)


def collect(entries):
    """진입 페이지에서 참조를 따라가며 올려야 할 파일을 모은다.

    사람이 목록을 적으면 언젠가 빠뜨린다. 페이지가 실제로 부르는 것을 따라가면
    빠뜨릴 수가 없다.
    """
    seen, missing, queue = set(), [], list(entries)
    while queue:
        rel = queue.pop()
        if rel in seen:
            continue
        seen.add(rel)
        f = ROOT / rel
        if not f.exists():
            missing.append((rel, "진입 페이지" if rel in entries else "참조됨"))
            continue
        if f.suffix.lower() not in (".html", ".js", ".css"):
            continue
        base = Path(rel).parent
        for m in REF.finditer(f.read_text(encoding="utf-8", errors="ignore")):
            ref = next((g for g in m.groups() if g), "")
            if not ref or ref.startswith(SKIP_PREFIX):
                continue
            if any(c in ref for c in ("${", "%", "<", ">", ",", " ")):
                continue
            if not ref.lower().endswith(FILE_EXT):
                continue
            # data/ 는 워크플로가 따로 관리한다(102MB) — 존재만 확인하고 목록에는 넣지 않는다
            target = (base / ref).as_posix().lstrip("./")
            target = re.sub(r"^(\./)+", "", target)
            if target.startswith("data/"):
                if not (ROOT / target).exists():
                    missing.append((target, f"{rel} 에서 참조"))
                continue
            if not (ROOT / target).exists():
                missing.append((target, f"{rel} 에서 참조"))
                continue
            queue.append(target)
    return sorted(seen), missing


def refs_to(files, target):
    """누가 이 파일을 부르고 있나. 딸려 온 파일을 지목만 하면 어디를 고쳐야
    할지 알 수 없다 — 부르는 쪽을 같이 알려 준다."""
    out = []
    for rel in files:
        f = ROOT / rel
        if rel == target or not f.exists() or f.suffix.lower() not in (".html", ".js", ".css"):
            continue
        base = Path(rel).parent
        for m in REF.finditer(f.read_text(encoding="utf-8", errors="ignore")):
            ref = next((g for g in m.groups() if g), "")
            if not ref or ref.startswith(SKIP_PREFIX):
                continue
            if re.sub(r"^(\./)+", "", (base / ref).as_posix().lstrip("./")) == target:
                out.append(rel)
                break
    return sorted(out)


def scan(files, checks, label):
    """파일들에서 금지 문구 / 자리표시자를 찾는다."""
    hits = []
    for rel in files:
        f = ROOT / rel
        if not f.exists() or f.suffix.lower() not in (".html", ".js", ".css"):
            continue
        text = f.read_text(encoding="utf-8", errors="ignore")
        for needle, why in checks:
            if needle not in text:
                continue
            if needle.startswith('content="noindex') and rel in NOINDEX_OK:
                continue
            hits.append((rel, why))
    return hits


def paid_ready():
    """publish_paid.py 를 돌렸는가 — 정적 파일에 유료 구간이 남아 있으면 안 된다."""
    d = ROOT / "data" / "reports_v2"
    if not d.exists():
        return None
    leaked = 0
    checked = 0
    for f in sorted(d.glob("*.json"))[:200]:
        try:
            rep = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if rep.get("v") != 2:
            continue
        checked += 1
        if rep.get("verdict") or rep.get("earnings"):
            leaked += 1
    return checked, leaked


def main():
    args = sys.argv[1:]
    paid = "--paid" in args
    check_only = "--check" in args
    dest = next((a for a in args if not a.startswith("--")), None)
    if not check_only and not dest:
        sys.exit(__doc__)

    entries = ENTRIES + (PAID_ENTRIES if paid else [])
    files, missing = collect(entries)

    log(f"## 실제 사이트 배포 검사 — 유료화 {'켬' if paid else '끔'}")
    log(f"- 올릴 파일 {len(files)}개 (진입 {len(entries)}개에서 참조를 따라가 수집)")

    bad = []

    if missing:
        bad.append("참조된 파일이 없음")
        log("\n❌ 없는 파일")
        for rel, why in sorted(set(missing)):
            log(f"   {rel}   ({why})")

    # 유료화를 끄고 배포하는데 결제 화면이 목록에 들어와 있으면 멈춘다.
    # PAID_ENTRIES 를 진입 페이지에서 빼는 것만으로는 못 막는다 — 모든 페이지
    # 머리말의 '멤버십' 링크를 타고 pricing.html 이 딸려 들어오고, 거기서
    # billing/checkout 과 결제 스크립트까지 줄줄이 끌려온다. 예전에 결제 화면이
    # 통째로 실제 사이트에 올라간 게 정확히 이 경로였다.
    if not paid:
        leaked = sorted(set(PAID_ENTRIES) & set(files))
        if leaked:
            bad.append("유료화를 껐는데 결제 화면이 딸려 옴")
            log("\n❌ 유료화를 끈 배포에 결제 화면이 섞였습니다")
            for rel in leaked:
                who = refs_to(files, rel)
                log(f"   {rel} ← {', '.join(who[:4]) if who else '진입 페이지'}"
                    + (f" 외 {len(who) - 4}개" if len(who) > 4 else ""))
            log("   유료화를 켜려면 --paid, 아직이라면 머리말·바닥글의 멤버십 링크를 먼저 빼세요.")

    forbidden = scan(files, FORBIDDEN, "금지")
    if forbidden:
        bad.append("스테이징 전용 코드가 섞임")
        log("\n❌ 실제 사이트에 있으면 안 되는 것")
        for rel, why in forbidden:
            log(f"   {rel} — {why}")

    holes = scan(files, PLACEHOLDERS, "자리표시자")
    if holes:
        # 유료화를 켤 때만 막는다. 그 전에는 사업자 정보가 없어도 사이트는 돈다.
        (bad if paid else []).append("자리표시자가 남아 있음")
        mark = "❌" if paid else "⚠️"
        log(f"\n{mark} 아직 채우지 않은 값")
        for rel, why in sorted(set(holes)):
            log(f"   {rel} — {why}")

    if paid:
        pr = paid_ready()
        if pr:
            checked, leaked = pr
            if leaked:
                bad.append("유료 구간이 정적 파일에 남아 있음")
                log(f"\n❌ publish_paid.py 를 아직 안 돌렸습니다 — 표본 {checked}개 중 {leaked}개에 "
                    f"유료 구간이 그대로 있습니다. 주소만 치면 전문이 나옵니다.")

    if bad:
        log("\n배포하지 않았습니다 — " + " / ".join(bad))
        sys.exit(1)

    log("\n✅ 검사 통과")
    if check_only:
        log("   (--check 모드라 복사하지 않았습니다)")
        return

    out = Path(dest).resolve()
    if not (out / ".git").exists():
        sys.exit(f"❌ {out} 는 git 체크아웃이 아닙니다.")
    n = 0
    for rel in files:
        dst = out / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, dst)
        n += 1
    log(f"- ✅ {n}개 복사 → {out}")
    log("   커밋·푸시는 직접 확인한 뒤에 하세요.")


if __name__ == "__main__":
    main()
