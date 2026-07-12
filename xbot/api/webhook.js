// X Activity API 웹훅 수신부.
// 역할은 딱 두 가지: ① CRC 검증(GET)에 즉시 답한다 ② 멘션 이벤트(POST)를 받으면
// 무조건 즉시 200을 반환하고, 실제 처리는 waitUntil로 /api/process에 넘긴다.
// (X는 3초 안에 응답 없으면 웹훅을 실패로 치고, 생성 파이프라인은 몇 분까지 걸릴 수 있음)
const crypto = require("crypto");
const { waitUntil } = require("@vercel/functions");

const BOT_HANDLE = (process.env.X_BOT_HANDLE || "kosai_x").toLowerCase();

function crcResponse(crcToken) {
  const hmac = crypto
    .createHmac("sha256", process.env.X_API_SECRET)
    .update(crcToken)
    .digest("base64");
  return { response_token: `sha256=${hmac}` };
}

// 이벤트 payload에서 "봇을 멘션한 남의 트윗"만 추린다.
function extractMentions(body) {
  const events = body.tweet_create_events || [];
  const out = [];
  for (const t of events) {
    const author = (t.user && t.user.screen_name) || "";
    if (author.toLowerCase() === BOT_HANDLE) continue; // 내 트윗(답글 포함) 무시
    if (t.retweeted_status) continue; // 리트윗 무시
    const text = t.truncated && t.extended_tweet ? t.extended_tweet.full_text : t.text || "";
    if (!text.toLowerCase().includes("@" + BOT_HANDLE)) continue;
    out.push({
      tweet_id: t.id_str,
      text,
      author_handle: author,
      author_id: t.user && t.user.id_str,
    });
  }
  return out;
}

module.exports = async (req, res) => {
  // ① CRC 검증 (X가 주기적으로 보냄)
  if (req.method === "GET") {
    const token = req.query.crc_token;
    if (!token) return res.status(400).json({ error: "no crc_token" });
    return res.status(200).json(crcResponse(token));
  }

  if (req.method !== "POST") return res.status(405).end();

  // (있을 때만) X 서명 검증 — 위조 요청 차단
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

  const mentions = extractMentions(req.body || {});
  const base = `https://${req.headers.host}`;
  for (const m of mentions) {
    waitUntil(
      fetch(`${base}/api/process`, {
        method: "POST",
        headers: {
          "content-type": "application/json",
          "x-internal-secret": process.env.INTERNAL_SECRET,
        },
        body: JSON.stringify(m),
      }).catch((e) => console.error("process 호출 실패:", e))
    );
  }
  // 처리 결과와 무관하게 즉시 200 — 재전송 폭주 방지
  return res.status(200).json({ ok: true, queued: mentions.length });
};
