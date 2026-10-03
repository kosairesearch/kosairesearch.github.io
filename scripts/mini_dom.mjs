/* ============================================================
   아주 작은 HTML 나무 — 영어 종목 페이지를 미리 번역할 때 쓴다(scripts/prerender_stock.mjs).

   번역은 브라우저와 같은 번역 엔진(i18n.js)의 walk 가 한다 — 엔진이 문서 대신 이 나무를 훑게 해서, 엔진이 고친 자리
   (글 조각 · 속성 · 덩어리)만 원래 HTML 문자열에서 바꿔 낸다. 고치지 않은 곳은 한 글자도 바뀌지 않는다.

   다루는 것은 우리 생성기가 만든 HTML(태그가 모두 제대로 닫힌 글)뿐이다. 브라우저처럼 잘못 닫힌 태그를 고쳐 읽지 않고,
   닫는 태그가 어긋나면 오류를 낸다 — 엉뚱하게 번역된 페이지를 내느니 그 종목을 실패로 두는 편이 낫다.
   엔진이 쓰는 만큼만 흉내 낸다: nodeType · tagName · id · 속성 읽기/쓰기 · firstChild · nextSibling · firstElementChild ·
   getElementsByTagName('*') · nodeValue 읽기/쓰기 · innerHTML 읽기/쓰기 · textContent 쓰기.
   ============================================================ */
const VOID = new Set(["area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"]);
const RAW = new Set(["script", "style", "textarea", "title"]);
const ENT = { amp: "&", lt: "<", gt: ">", quot: '"', apos: "'", nbsp: " ", "#39": "'" };

export function decode(s) {
  return s.replace(/&(#x[0-9a-fA-F]+|#\d+|[a-zA-Z]+|#39);/g, (m, e) => {
    if (e[0] === "#") { const n = e[1] === "x" || e[1] === "X" ? parseInt(e.slice(2), 16) : parseInt(e.slice(1), 10); return Number.isFinite(n) ? String.fromCodePoint(n) : m; }
    return Object.prototype.hasOwnProperty.call(ENT, e) ? ENT[e] : m;
  });
}
export const escText = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
export const escAttr = (s) => String(s).replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

class Node {
  get nextSibling() { const p = this.parentNode; return p ? p.childNodes[this._i + 1] || null : null; }
  get parentElement() { return this.parentNode && this.parentNode.nodeType === 1 ? this.parentNode : null; }
}
class Text extends Node {
  constructor(doc, start, end, value) { super(); this.nodeType = 3; this._doc = doc; this._s = start; this._e = end; this._v = value; }
  get nodeValue() { return this._v; }
  set nodeValue(v) { v = String(v); if (v === this._v) return; this._v = v; this._doc._edit(this._s, this._e, escText(v)); }
  get textContent() { return this._v; }
}
class Comment extends Node { constructor() { super(); this.nodeType = 8; } }
class Element extends Node {
  constructor(doc, name, svg) {
    super();
    this.nodeType = 1; this._doc = doc; this.localName = name;
    this.tagName = svg ? name : name.toUpperCase();   // 브라우저처럼 — HTML 요소는 대문자, SVG 안의 요소는 적은 그대로
    this.childNodes = []; this._attrs = []; this._a0 = this._a1 = this._c0 = this._c1 = 0;
  }
  _find(n) { n = String(n).toLowerCase(); return this._attrs.find((a) => a.name === n) || null; }
  hasAttribute(n) { return !!this._find(n); }
  getAttribute(n) { const a = this._find(n); return a ? a.value : null; }
  setAttribute(n, v) {
    const a = this._find(n); v = String(v);
    if (!a) throw new Error(`mini_dom: 없는 속성을 새로 달 수 없다(${this.localName}@${n})`);
    if (a.value === v) return;
    a.value = v; this._doc._edit(a.s, a.e, `${a.name}="${escAttr(v)}"`);
  }
  get id() { return this.getAttribute("id") || ""; }
  get firstChild() { return this.childNodes[0] || null; }
  get firstElementChild() { return this.childNodes.find((c) => c.nodeType === 1) || null; }
  getElementsByTagName(t) {
    const out = [], want = t === "*" ? null : String(t).toUpperCase();
    (function rec(el) { for (const c of el.childNodes) if (c.nodeType === 1) { if (!want || c.tagName.toUpperCase() === want) out.push(c); rec(c); } })(this);
    return out;
  }
  get innerHTML() { return this._doc.src.slice(this._c0, this._c1); }
  set innerHTML(v) { this._doc._edit(this._c0, this._c1, String(v)); }
  set textContent(v) { this._doc._edit(this._c0, this._c1, escText(v)); }
  get textContent() { let s = ""; (function rec(el) { for (const c of el.childNodes) { if (c.nodeType === 3) s += c.nodeValue; else if (c.nodeType === 1) rec(c); } })(this); return s; }
}

/* 조각 하나(본문 · 머리 · 꼬리)를 나무로. body 는 조각 전체를 담는 가짜 <body> 다. */
export function parse(src) {
  const doc = {
    src, edits: [],
    _edit(s, e, text) { this.edits.push({ s, e, text }); },
  };
  const body = new Element(doc, "body", false);
  body._c0 = 0; body._c1 = src.length;
  const stack = [{ el: body, svg: false }];
  const add = (n) => { const top = stack[stack.length - 1].el; n.parentNode = top; n._i = top.childNodes.length; top.childNodes.push(n); };
  let i = 0;
  const n = src.length;
  while (i < n) {
    const lt = src.indexOf("<", i);
    const next = lt < 0 ? n : lt;
    if (next > i) { add(new Text(doc, i, next, decode(src.slice(i, next)))); i = next; continue; }
    // 여기서 src[i] === '<'
    if (src.startsWith("<!--", i)) {
      const e = src.indexOf("-->", i + 4);
      if (e < 0) throw new Error("mini_dom: 닫히지 않은 주석");
      add(new Comment()); i = e + 3; continue;
    }
    if (src[i + 1] === "/") {
      const e = src.indexOf(">", i);
      if (e < 0) throw new Error("mini_dom: 닫히지 않은 닫는 태그");
      const name = src.slice(i + 2, e).trim().toLowerCase();
      const top = stack[stack.length - 1];
      if (stack.length < 2 || top.el.localName !== name) throw new Error(`mini_dom: 닫는 태그가 어긋난다 — </${name}> (열린 것: <${top.el.localName}>) @${i}`);
      top.el._c1 = i; stack.pop(); i = e + 1; continue;
    }
    if (!/[A-Za-z]/.test(src[i + 1] || "")) { add(new Text(doc, i, i + 1, "<")); i += 1; continue; }   // 글 안의 '<'(우리 HTML 에는 없다)
    // 여는 태그
    const m = /^<([A-Za-z][A-Za-z0-9-]*)/.exec(src.slice(i, i + 64));
    const name = m[1].toLowerCase();
    let j = i + m[0].length;
    const svg = stack[stack.length - 1].svg || name === "svg";
    const el = new Element(doc, name, svg);
    let selfClose = false;
    for (;;) {
      while (j < n && /\s/.test(src[j])) j++;
      if (src[j] === ">") { j++; break; }
      if (src[j] === "/" && src[j + 1] === ">") { selfClose = true; j += 2; break; }
      if (j >= n) throw new Error("mini_dom: 닫히지 않은 여는 태그");
      const am = /^([^\s"'>\/=]+)/.exec(src.slice(j, j + 256));
      if (!am) throw new Error(`mini_dom: 속성을 읽지 못했다 @${j}`);
      const as = j, aname = am[1].toLowerCase();
      j += am[1].length;
      let k = j; while (k < n && /\s/.test(src[k])) k++;
      let value = "";
      if (src[k] === "=") {
        k++; while (k < n && /\s/.test(src[k])) k++;
        const q = src[k];
        if (q === '"' || q === "'") { const e = src.indexOf(q, k + 1); if (e < 0) throw new Error("mini_dom: 닫히지 않은 따옴표"); value = decode(src.slice(k + 1, e)); j = e + 1; }
        else { const vm = /^[^\s>]+/.exec(src.slice(k)); value = decode(vm ? vm[0] : ""); j = k + (vm ? vm[0].length : 0); }
      }
      el._attrs.push({ name: aname, value, s: as, e: j });
    }
    el._a0 = i; el._a1 = j;
    add(el);
    if (selfClose || VOID.has(name)) { el._c0 = el._c1 = j; i = j; continue; }
    if (RAW.has(name)) {
      const e = src.toLowerCase().indexOf("</" + name, j);
      if (e < 0) throw new Error(`mini_dom: 닫히지 않은 <${name}>`);
      el._c0 = j; el._c1 = e;
      if (e > j) { const t = new Text(doc, j, e, src.slice(j, e)); t.parentNode = el; t._i = 0; el.childNodes.push(t); }
      i = src.indexOf(">", e) + 1; continue;
    }
    el._c0 = j; stack.push({ el, svg }); i = j;
  }
  if (stack.length !== 1) throw new Error(`mini_dom: 닫히지 않은 태그 <${stack[stack.length - 1].el.localName}>`);
  return { body, doc };
}

/* 엔진이 고친 자리를 원래 글에 끼운다. 겹치는 고침은 없어야 한다(덩어리를 통째로 바꾼 뒤에는 그 안을 다시 고치지 않는다). */
export function serialize({ doc }) {
  const ed = doc.edits.slice().sort((a, b) => a.s - b.s || a.e - b.e);
  let out = "", at = 0;
  for (const x of ed) {
    if (x.s < at) throw new Error(`mini_dom: 고친 자리가 겹친다 @${x.s}`);
    out += doc.src.slice(at, x.s) + x.text; at = x.e;
  }
  return out + doc.src.slice(at);
}
