/* ============================================================
   영어 화면에 한국어가 남는 자리를 찾는다  (실사이트 + 스테이징)

   왜 있는가. 화면 문구는 두 군데에 나뉘어 있다 — 사전에 번역을 등록하고,
   본문에서 T("…") 로 부른다. 둘 중 하나만 손대면 그 문구는 영어 화면에서
   한국어 그대로 나온다. 한국어로 보면 멀쩡하니 눈으로는 잘 안 걸린다.

   실제로 셋이 그렇게 빠져 있었다.

     "결제 수단이 변경되었습니다. 다음 결제일부터 새 카드로 청구됩니다."
     "로그인"
     "이미 다른 방법으로 가입된 이메일입니다."

   말투를 손보다 우연히 걸렸지, 찾으려고 찾은 게 아니다. 우연에 기대지
   않으려고 남긴다.

   반대쪽(아무도 안 쓰는 번역이 사전에 남아 있는가)은 보지 않는다. 문구를
   T("…") 로만 부르는 게 아니라 kv(dl, "상태", …) 처럼 넘겨주고 안에서
   번역하는 자리가 많아서, 세어 보면 멀쩡한 줄이 무더기로 걸린다. 틀린
   기준으로 실패하는 검사는 없는 것보다 나쁘다.

   실행
     node scripts/check_i18n.mjs
   ============================================================ */
import { readFileSync, readdirSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const DIRS = [["실사이트", ROOT], ["스테이징", join(ROOT, "staging")]];

const KO = /[가-힣]/;
/* 사전 한 줄: "한국어": "English" — 값이 한국어면 사전이 아니라 그냥 자료다. */
const KEYS = /"((?:[^"\\]|\\.)*[가-힣](?:[^"\\]|\\.)*)"\s*:\s*"((?:[^"\\]|\\.)*)"/g;
const USES = /\bT\(\s*"((?:[^"\\]|\\.)*[가-힣](?:[^"\\]|\\.)*)"/g;

let missing = 0, checked = 0;

for (const [label, dir] of DIRS) {
  if (!existsSync(dir)) continue;
  const files = readdirSync(dir).filter((f) => f.endsWith(".js"));
  for (const f of files) {
    const s = readFileSync(join(dir, f), "utf8");
    const keys = new Set(), used = new Set();
    for (const m of s.matchAll(KEYS)) if (!KO.test(m[2])) keys.add(m[1]);
    for (const m of s.matchAll(USES)) used.add(m[1]);
    if (!used.size) continue;                    // 번역을 안 쓰는 파일
    checked++;

    const miss = [...used].filter((u) => !keys.has(u));
    if (miss.length) {
      missing += miss.length;
      console.log(`\n  ${label}/${f} — 번역이 없다`);
      miss.forEach((m) => console.log("     " + m));
    }
  }
}

console.log("");
if (missing) {
  console.log(`FAIL  영어 화면에 한국어가 남는 문구 ${missing}개 (파일 ${checked}개 확인)`);
  process.exit(1);
}
console.log(`PASS  영어 화면에 한국어가 남는 문구 없음 (파일 ${checked}개 확인)`);
