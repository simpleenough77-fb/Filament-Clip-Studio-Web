// Anonymous feedback for filamentclip.com: POST /api/feedback (routed from worker/stat.js).
// Nothing here ever reads feedback back out to a page, so stored text is never rendered on the site.
// Defense in depth anyway: every field is checked against an allowlist or normalized to plain text,
// and every query is parameterized.
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
export function normalizeComment(input) {
  if (typeof input !== 'string') return null;
  let s = input.slice(0, MAX_COMMENT * 4).normalize('NFKC');
  s = s.replace(/[\p{Cf}\p{Co}\p{Cs}\p{Cn}]/gu, '');   // invisible, bidi-override, private-use and unassigned characters
  s = s.replace(/\s+/gu, ' ');                           // newlines, tabs and odd spaces become one plain space
  s = s.replace(/\p{Cc}/gu, '');                         // any remaining control characters (NUL, BEL, ...)
  s = s.replace(/[<>]/g, '').trim();
  s = [...s].slice(0, MAX_COMMENT).join('').trim();
  if (/^[=+\-@]/.test(s)) s = "'" + s; // keeps CSV and Google Sheets exports from treating it as a formula
  return s === '' ? null : s;
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
  await env.DB.prepare(
    'INSERT INTO feedback (ts, source, rating, tags, comment) VALUES (?, ?, ?, ?, ?)'
  ).bind(now, f.source, f.rating, f.tags, f.comment).run();
  return json({ ok: true }, 202, extra);
}
