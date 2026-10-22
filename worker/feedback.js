// Anonymous feedback for filamentclip.com (routed from worker/stat.js):
//   POST /api/feedback  store one response
//   GET  /api/feedback  public summary and the latest responses, for the Feedback page
// Stored text is only ever served as JSON data and the page shows it with textContent, never as markup. Defense in depth:
// every field is checked against an allowlist or normalized to plain text on the way in, normalized again on the way out
// (so a row edited by hand in the D1 console is still safe), and every query is parameterized.
export const SOURCES = new Set(['download', 'page']);
// Keep in step with TAGS in feedback.js (tests/test_feedback.mjs checks that they match).
export const TAGS = new Set(['easy', 'fit', 'readable', 'holders', 'slicer', 'slow', 'confusing', 'missing', 'bug']);
export const MAX_COMMENT = 500;
const MAX_BODY_BYTES = 4096;
const MAX_PER_MINUTE = 60;   // global circuit breakers; no per-visitor tracking
const MAX_PER_DAY = 1000;

// Plain text only: Unicode NFKC (so look-alike and full-width characters become ordinary ones), all whitespace
// collapsed to single spaces, control / invisible / bidi-override / private-use characters removed, angle brackets
// removed, a leading spreadsheet-formula character defused, and a hard length cap in characters.
export const MAX_REPLY = 600;
export function normalizeComment(input, max = MAX_COMMENT) {
  if (typeof input !== 'string') return null;
  let s = input.slice(0, max * 4).normalize('NFKC');
  s = s.replace(/[\p{Cf}\p{Co}\p{Cs}\p{Cn}]/gu, '');   // invisible, bidi-override, private-use and unassigned characters
  s = s.replace(/\s+/gu, ' ');                           // newlines, tabs and odd spaces become one plain space
  s = s.replace(/\p{Cc}/gu, '');                         // any remaining control characters (NUL, BEL, ...)
  s = s.replace(/[<>]/g, '').trim();
  s = [...s].slice(0, max).join('').trim();
  if (/^[=+\-@]/.test(s)) s = "'" + s; // keeps CSV and Google Sheets exports from treating it as a formula
  return s === '' ? null : s;
}

// ---- moderation ----------------------------------------------------------------------------------------------
// A flagged comment is still stored, but the public page withholds its text until the owner approves it (README, "Feedback").
// The rating and topics are never withheld. Flags: 'spam' (row is also hidden), 'link', 'language', 'caps', 'duplicate'.
// None of this is meant to be perfect: held comments are reviewed by a person, and the page shows text as inert text anyway.
// Keep this list short and clearly abusive; mild swearing about a failed print is legitimate feedback.
export const PROFANITY = ['fuck', 'shit', 'bitch', 'bastard', 'asshole', 'ass', 'dick', 'cock', 'pussy', 'cunt', 'slut', 'whore', 'nigger', 'nigga', 'faggot', 'retard', 'kys'];
const SPAM_PHRASES = /\b(?:casino|viagra|bitcoin|crypto|forex|backlinks?|seo services?|whatsapp|telegram|click here|free money|work from home|loan offer)\b/i;
const TLDS = 'com|net|org|io|co|me|ly|xyz|top|info|biz|shop|site|online|store|app|dev|ru|cn|tk|ml|ga|cf|gg|tv|us|uk|de|fr|ws|cc|link|click';
const LINKS = [
  /\b(?:https?:\/\/|ftp:\/\/|www\.)/i,                                                         // URLs
  new RegExp(`\\b[a-z0-9-]{2,}(?:\\.[a-z0-9-]+)*\\.(?:${TLDS})\\b`, 'i'),                          // bare domains
  /\b[a-z0-9-]+\s*[([{]?\s*dot\s*[)\]}]?\s*(?:com|net|org|io|co)\b/i,                         // "example dot com"
  /[a-z0-9._%+-]+\s*(?:@|[([]at[)\]])\s*[a-z0-9-]+(?:\.|\s*[([]dot[)\]]\s*)[a-z]{2,}/i,      // email addresses
  /(?:^|\s)@[a-z0-9_.]{3,}/i,                                                                  // @handles
  /(?:\+?\d{1,3}[\s.-]?)?(?:\(\d{3}\)|\d{3})[\s.-]?\d{3}[\s.-]?\d{4}\b/,                      // phone numbers
];
const LEET = { 0: 'o', 1: 'i', 3: 'e', 4: 'a', 5: 's', 7: 't', '@': 'a', $: 's', '!': 'i' };
// Whole words only (so "class" or "assembly" are fine), a letter may be stretched ("fuuuck", "sh1t"), common endings allowed.
// "ass" -> a{1,}s{2,}: each run of identical letters may be stretched but never shortened.
const stretch = (w) => (w.match(/(.)\1*/g) || []).map((run) => `${run[0]}{${run.length},}`).join('');
const WORDS = new RegExp('\\b(?:' + PROFANITY.map(stretch).join('|') + ')(?:s|es|ed|ing|er|ers|y)?\\b');

export function hasProfanity(comment) {
  const t = comment.toLowerCase().replace(/[013457@$!]/g, (c) => LEET[c]);
  if (WORDS.test(t)) return true;
  // "f u c k", "s.h.i.t": single letters separated by spaces or punctuation, joined back together
  for (const m of t.matchAll(/(?:^|[^a-z])((?:[a-z][\s.*_-]+){2,}[a-z])(?![a-z])/g)) {
    if (WORDS.test(m[1].replace(/[\s.*_-]+/g, ''))) return true;
  }
  return false;
}

export function moderate(comment) {
  if (typeof comment !== 'string' || comment === '') return null;
  const letters = comment.replace(/[^\p{L}]/gu, '');
  const capsShare = letters.length >= 20 ? (comment.match(/\p{Lu}/gu) || []).length / letters.length : 0;
  if (SPAM_PHRASES.test(comment) || /([\p{L}\p{N}])\1{9,}/u.test(comment)) return 'spam';
  if (LINKS.some((re) => re.test(comment))) return 'link';
  if (hasProfanity(comment)) return 'language';
  if (capsShare > 0.8) return 'caps'; // probably just enthusiasm: held for a look, the rating still counts
  return null;
}

// Returns {spam: true} for a filled-in honeypot, null for an invalid submission, or the record to store.
export function cleanFeedback(body) {
  if (!body || typeof body !== 'object' || Array.isArray(body)) return null;
  if (typeof body.website === 'string' && body.website !== '') return { spam: true };
  const rating = body.rating;
  if (!Number.isInteger(rating) || rating < 1 || rating > 5) return null;
  if (typeof body.source !== 'string' || !SOURCES.has(body.source)) return null;
  const picked = new Set();
  if (Array.isArray(body.tags)) {
    for (const t of body.tags.slice(0, 20)) if (typeof t === 'string' && TAGS.has(t)) picked.add(t);
  }
  return {
    rating,
    source: body.source,
    tags: JSON.stringify([...picked].sort()),
    comment: normalizeComment(body.comment),
  };
}

// Reads at most `limit` bytes of the body; returns null if the body is larger.
async function readLimited(request, limit) {
  const declared = Number(request.headers.get('Content-Length'));
  if (Number.isFinite(declared) && declared > limit) return null;
  if (!request.body) return '';
  const reader = request.body.getReader();
  const chunks = [];
  let size = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    size += value.byteLength;
    if (size > limit) { await reader.cancel(); return null; }
    chunks.push(value);
  }
  const all = new Uint8Array(size);
  let at = 0;
  for (const c of chunks) { all.set(c, at); at += c.byteLength; }
  return new TextDecoder().decode(all);
}

function originAllowed(request, hosts) {
  const origin = request.headers.get('Origin');
  if (!origin) return false;
  try { return hosts.has(new URL(origin).hostname); } catch { return false; }
}

export async function handleFeedback(request, env, { HOSTS, json }) {
  const extra = { 'X-Content-Type-Options': 'nosniff' };
  // Same-site pages only. A cross-site page cannot send application/json without a CORS preflight, and no CORS
  // headers are ever returned, so another site cannot post here from a visitor's browser. There are no cookies to ride on.
  if (!originAllowed(request, HOSTS)) return json({ ok: false }, 403, extra);
  if (!/^application\/json\b/i.test(request.headers.get('Content-Type') || '')) return json({ ok: false }, 415, extra);
  const text = await readLimited(request, MAX_BODY_BYTES);
  if (text === null) return json({ ok: false }, 413, extra);
  let body;
  try { body = JSON.parse(text); } catch { return json({ ok: false }, 400, extra); }
  const f = cleanFeedback(body);
  if (!f) return json({ ok: false }, 400, extra);
  if (f.spam) return json({ ok: true }, 202, extra); // honeypot: pretend it worked, store nothing

  const now = Math.floor(Date.now() / 1000);
  const recent = await env.DB.prepare(
    'SELECT SUM(ts > ?) AS minute, COUNT(*) AS day FROM feedback WHERE ts > ?'
  ).bind(now - 60, now - 86400).first();
  if (recent && ((recent.minute || 0) >= MAX_PER_MINUTE || recent.day >= MAX_PER_DAY)) {
    return json({ ok: false }, 429, { ...extra, 'Retry-After': '60' });
  }
  let flag = moderate(f.comment);
  if (f.comment && !flag) {
    const same = await env.DB.prepare('SELECT 1 AS dup FROM feedback WHERE comment = ? AND ts > ? LIMIT 1').bind(f.comment, now - 86400).first();
    if (same) flag = 'duplicate';
  }
  // The visitor always gets the same "thanks"; a flagged comment is just held back. Spam is not listed or counted at all.
  await env.DB.prepare(
    'INSERT INTO feedback (ts, source, rating, tags, comment, flag, hidden) VALUES (?, ?, ?, ?, ?, ?, ?)'
  ).bind(now, f.source, f.rating, f.tags, f.comment, flag, flag === 'spam' ? 1 : 0).run();
  return json({ ok: true }, 202, extra);
}

// ---- reading -------------------------------------------------------------------------------------------------
const LIST_LIMIT = 100;

// One stored row as the public sees it: no id, no time of day, only values that pass the same checks as on the way in.
export function publicItem(row) {
  if (!row || !Number.isInteger(row.rating) || row.rating < 1 || row.rating > 5) return null;
  let tags = [];
  try {
    const parsed = JSON.parse(row.tags);
    if (Array.isArray(parsed)) tags = [...new Set(parsed.filter((t) => typeof t === 'string' && TAGS.has(t)))].sort();
  } catch { /* unreadable tags are shown as none */ }
  const date = Number.isFinite(row.ts) ? new Date(row.ts * 1000).toISOString().slice(0, 10) : null;
  const item = { date, rating: row.rating, tags, comment: normalizeComment(row.comment) };
  // The owner's reply (README, "Feedback"), written by hand in the D1 console; it gets the same cleaning as visitor text.
  const reply = normalizeComment(row.reply, MAX_REPLY);
  if (reply) {
    item.reply = reply;
    item.reply_date = Number.isFinite(row.reply_ts) ? new Date(row.reply_ts * 1000).toISOString().slice(0, 10) : null;
  }
  return item;
}

export async function listFeedback(request, env, ctx, { json }) {
  const cache = typeof caches !== 'undefined' ? caches.default : null;
  const key = new Request(new URL('/api/feedback', request.url).href); // the query string never changes the answer
  if (cache) { const hit = await cache.match(key); if (hit) return hit; }
  const total = await env.DB.prepare(
    'SELECT COUNT(*) AS n, COALESCE(AVG(rating), 0) AS average, COALESCE(SUM(rating = 1), 0) AS r1, COALESCE(SUM(rating = 2), 0) AS r2, COALESCE(SUM(rating = 3), 0) AS r3, COALESCE(SUM(rating = 4), 0) AS r4, COALESCE(SUM(rating = 5), 0) AS r5 FROM feedback WHERE hidden = 0'
  ).first();
  const { results } = await env.DB.prepare(
    'SELECT ts, rating, tags, CASE WHEN flag IS NULL THEN comment END AS comment, reply, reply_ts FROM feedback WHERE hidden = 0 ORDER BY id DESC LIMIT ?'
  ).bind(LIST_LIMIT).all();
  const body = {
    count: total ? total.n : 0,
    average: total ? Math.round(total.average * 10) / 10 : 0,
    counts: total ? [total.r1, total.r2, total.r3, total.r4, total.r5] : [0, 0, 0, 0, 0],
    items: (results || []).map(publicItem).filter(Boolean),
  };
  // No Access-Control-Allow-Origin: only the site's own pages can read this from a browser.
  const res = json(body, 200, { 'Cache-Control': 'public, max-age=60', 'X-Content-Type-Options': 'nosniff' });
  if (cache) ctx.waitUntil(cache.put(key, res.clone()));
  return res;
}
