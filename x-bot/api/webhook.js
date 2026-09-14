// X Activity API 웹훅 수신부 — 멘션 실시간 수신(폴링 대체).
// ① GET: CRC 검증(HMAC-SHA256, consumer secret) 즉시 응답
// ② POST: 서명 검증(HMAC-SHA256, 원본 본문) → 멘션 이벤트 → 중복체크(SET NX) → Redis 큐 적재 → /api/work 깨우기 → 즉시 200
// 무거운 생성·게시는 전부 work(Python, maxDuration 300s)가 한다. X는 수 초 안에
// 응답이 없으면 웹훅을 실패 처리하므로 여기서는 절대 기다리지 않는다.
//
// 이벤트 형식은 구형(AAA: tweet_create_events)과 신형(v2: data/includes) 둘 다 받는다.
// 디버깅용으로 마지막 수신 payload를 Redis(debug:last_event)에 24시간 보관 —
// 파싱이 안 맞으면 /api/health 로 확인해 맞춘다.
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

// 다양한 필드명에서 첫 값을 꺼낸다(형식 방어).
const pick = (o, keys) => {
  for (const k of keys) if (o && o[k] != null && o[k] !== "") return o[k];
  return null;
};

// author_id → username (v2 includes.users에서)
function userById(body, id) {
  const users = (body.includes && body.includes.users) || body.users || [];
  const u = users.find((x) => String(x.id) === String(id));
  return u ? u.username || u.screen_name : null;
}

function candidateAuthor(t, body) {
  if (t.user) return t.user.screen_name || t.user.username;
  if (t.author) return t.author.username || t.author.screen_name || t.author.userName;
  if (t.author_id) return userById(body, t.author_id);
  return null;
}

// 이벤트 payload에서 "봇을 멘션한 남의 트윗"들을 추린다 — 구형·신형 모두.
function extractMentions(body) {
  const out = [];
  const seen = new Set();

  const consider = (t, requireBotMention) => {
    if (!t || typeof t !== "object") return;
    const id = pick(t, ["id_str", "id"]);
    const text =
      t.truncated && t.extended_tweet
        ? t.extended_tweet.full_text
        : pick(t, ["text", "full_text"]);
    if (!id || !text || seen.has(String(id))) return;
    if (t.retweeted_status) return;
    const author = (candidateAuthor(t, body) || "").toLowerCase();
    if (author === BOT) return; // 내 답글이 다시 이벤트로 오는 것 무시
    if (requireBotMention && !text.toLowerCase().includes("@" + BOT)) return;
    seen.add(String(id));
    out.push({ id: String(id), text, attempts: 0 });
  };

  // 구형(AAA) — 계정의 모든 트윗이 오므로 @봇 포함 여부를 확인
  for (const t of body.tweet_create_events || []) consider(t, true);
  // 신형(v2) — 구독 자체가 'Post Mention Create'라 이미 멘션만 옴
  const d = body.data;
  if (Array.isArray(d)) for (const t of d) consider(t, false);
  else if (d) consider(d, false);
  for (const t of body.posts || body.tweets || []) consider(t, false);
  if (body.post) consider(body.post, false);
  if (body.tweet) consider(body.tweet, false);
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

/* 본문을 원본 바이트 그대로 읽는다.

   X 는 서명을 원본 본문으로 만든다. Vercel 이 미리 JSON 으로 풀어 버리면
   되돌린 문자열은 원본과 달라 검증할 수 없다 — 그래서 예전에는 검증을
   포기하고 '참고용' 으로만 적었다. 파싱을 끄면 원본이 그대로 온다. */
function readRaw(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    req.on("data", (c) => chunks.push(Buffer.isBuffer(c) ? c : Buffer.from(c)));
    req.on("end", () => resolve(Buffer.concat(chunks)));
    req.on("error", reject);
  });
}

/* x-twitter-webhooks-signature: "sha256=" + base64(HMAC-SHA256(consumer secret, 본문)).
   길이가 다르면 timingSafeEqual 이 던지므로 먼저 길이를 본다. */
function signatureOk(raw, header) {
  const secret = process.env.X_API_SECRET || "";
  if (!secret || !header) return false;
  const expect = "sha256=" + crypto.createHmac("sha256", secret).update(raw).digest("base64");
  const a = Buffer.from(String(header));
  const b = Buffer.from(expect);
  return a.length === b.length && crypto.timingSafeEqual(a, b);
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

  // ② 서명 검증 — X 가 보낸 것만 받는다.
  //    이게 없으면 이 주소를 아는 누구나 가짜 '멘션' 을 밀어 넣어, 봇이
  //    아무 트윗에나 답글을 달게 만들 수 있다(생성 비용은 우리가 문다).
  //    도착 기록은 검증 결과와 무관하게 먼저 남긴다 — 이벤트가 오는데 서명이
  //    안 맞으면 /api/health 의 last_sig 가 'bad' 로 보이게.
  const raw = await readRaw(req);
  const sig = req.headers["x-twitter-webhooks-signature"];
  const sigOk = signatureOk(raw, sig);
  try {
    await redis("SET", "debug:last_event_at", new Date().toISOString(), "EX", 86400);
    await redis("SET", "debug:last_sig", sigOk ? "ok" : (sig ? "bad" : "missing"), "EX", 86400);
  } catch (e) {
    console.error("redis 오류:", e);
  }
  if (!sigOk) return res.status(401).json({ error: "bad signature" });

  let body;
  try { body = JSON.parse(raw.toString("utf8") || "{}") || {}; }
  catch (_) { return res.status(400).json({ error: "bad json" }); }

  const mentions = extractMentions(body);
  let queued = 0;
  try {
    await redis("SET", "debug:last_event",
      JSON.stringify(body).slice(0, 4000), "EX", 86400);
    await redis("SET", "debug:last_parsed", String(mentions.length), "EX", 86400);
    for (const m of mentions) {
      const fresh = await redis("SET", `proc:${m.id}`, "1", "NX", "EX", PROC_TTL);
      if (fresh !== "OK") continue; // 이미 처리/예약된 멘션
      await redis("RPUSH", "jobs", JSON.stringify(m));
      queued++;
    }
  } catch (e) {
    console.error("redis 오류:", e);
  }
  if (queued) waitUntil(kickWork(req.headers.host));
  return res.status(200).json({ ok: true, parsed: mentions.length, queued });
};

// 본문 파싱을 끈다 — 위 readRaw 가 원본을 읽어야 서명을 검증할 수 있다.
module.exports.config = { api: { bodyParser: false } };
