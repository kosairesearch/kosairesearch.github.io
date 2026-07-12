// X Activity API 웹훅 수신부 — 멘션 실시간 수신(폴링 대체).
// ① GET: CRC 검증(HMAC-SHA256, consumer secret) 즉시 응답
// ② POST: 멘션 이벤트 → 중복체크(SET NX) → Redis 큐 적재 → /api/work 깨우기 → 즉시 200
// 무거운 생성·게시는 전부 work(Python, maxDuration 300s)가 한다. X는 수 초 안에
// 응답이 없으면 웹훅을 실패 처리하므로 여기서는 절대 기다리지 않는다.
const crypto = require("crypto");
const { waitUntil } = require("@vercel/functions");

const BOT = (process.env.BOT_HANDLE || "kosai_x").replace(/^@/, "").toLowerCase();
const PROC_TTL = 7 * 24 * 3600; // store.py PROC_TTL과 동일(처리 멘션ID 7일 보관)

async function redis(...args) {
  const r = await fetch(process.env.UPSTASH_REDIS_REST_URL, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${process.env.UPSTASH_REDIS_REST_TOKEN}`,
      "content-type": "application/json",
    },
    body: JSON.stringify(args.map(String)),
  });
  return (await r.json()).result;
}

// 이벤트 payload에서 "봇을 멘션한 남의 원본 트윗"만 추린다.
function extractMentions(body) {
  const out = [];
  for (const t of body.tweet_create_events || []) {
    const author = ((t.user && t.user.screen_name) || "").toLowerCase();
    if (!t.id_str || author === BOT) continue; // 내 답글이 다시 이벤트로 오는 것 무시
    if (t.retweeted_status) continue;
    const text =
      t.truncated && t.extended_tweet ? t.extended_tweet.full_text : t.text || "";
    if (!text.toLowerCase().includes("@" + BOT)) continue;
    out.push({ id: t.id_str, text, attempts: 0 });
  }
  return out;
}

// work를 '기다리지 않고' 깨운다 — 요청이 Vercel에 닿기만 하면 함수는 끝까지 실행됨.
async function kickWork(host) {
  const url = `https://${host}/api/work?key=${encodeURIComponent(
    process.env.POLL_SECRET || ""
  )}`;
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), 5000);
  try {
    await fetch(url, { signal: ctl.signal });
  } catch (_) {
    /* 5초 후 끊는 게 정상 — work는 계속 돈다 */
  } finally {
    clearTimeout(timer);
  }
}

module.exports = async (req, res) => {
  // ① CRC 검증 (등록 시 + X가 주기적으로 보냄)
  if (req.method === "GET") {
    const token = req.query.crc_token;
    if (!token) return res.status(400).json({ error: "no crc_token" });
    const hmac = crypto
      .createHmac("sha256", process.env.X_API_SECRET)
      .update(token)
      .digest("base64");
    return res.status(200).json({ response_token: `sha256=${hmac}` });
  }
  if (req.method !== "POST") return res.status(405).end();

  // (헤더가 있을 때만) X 서명 검증 — 위조 이벤트 차단
  const sig = req.headers["x-twitter-webhooks-signature"];
  if (sig) {
    const expected =
      "sha256=" +
      crypto
        .createHmac("sha256", process.env.X_API_SECRET)
        .update(JSON.stringify(req.body))
        .digest("base64");
    if (sig !== expected) return res.status(401).end();
  }

  let queued = 0;
  for (const m of extractMentions(req.body || {})) {
    try {
      const fresh = await redis("SET", `proc:${m.id}`, "1", "NX", "EX", PROC_TTL);
      if (fresh !== "OK") continue; // 이미 처리/예약된 멘션
      await redis("RPUSH", "jobs", JSON.stringify(m));
      queued++;
    } catch (e) {
      console.error("redis 오류:", e);
    }
  }
  if (queued) waitUntil(kickWork(req.headers.host));
  return res.status(200).json({ ok: true, queued });
};
