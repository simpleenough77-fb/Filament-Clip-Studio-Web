// Anonymous usage counter for filamentclip.com.
// Only /api/* reaches this Worker (assets.run_worker_first in wrangler.jsonc); everything else is static.
//   POST /api/stat   one event per generated batch (fire-and-forget from the studio)
//   GET  /api/stats  public totals, cached for 5 minutes
const HOSTS = new Set(['filamentclip.com', 'www.filamentclip.com']);
const MAX_PER_MINUTE = 120; // global circuit breaker; no per-visitor tracking

const json = (body, status = 200, extra = {}) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store', ...extra },
  });

const int = (v, min, max) => (Number.isInteger(v) && v >= min && v <= max ? v : null);

function clean(body) {
  const clips = int(body.clips, 1, 100);
  if (clips === null) return null;
  const holders = int(body.holders ?? 0, 0, 200);
  const plates = int(body.plates ?? 0, 0, 50);
  if (holders === null || plates === null) return null;
  const printer = typeof body.printer === 'string' && /^[A-Za-z0-9_ .-]{1,24}$/.test(body.printer) ? body.printer : null;
  const vendors = {};
  if (body.vendors && typeof body.vendors === 'object' && !Array.isArray(body.vendors)) {
    for (const [name, n] of Object.entries(body.vendors).slice(0, 12)) {
      if (/^[\p{L}\p{N} .&+'-]{1,40}$/u.test(name) && int(n, 1, 100) !== null) vendors[name] = n;
    }
  }
  return { clips, holders, plates, printer, nfc: body.nfc ? 1 : 0, sleeve: body.sleeve ? 1 : 0, vendors: JSON.stringify(vendors) };
}

async function record(request, env) {
  const origin = request.headers.get('Origin');
  if (!origin || !HOSTS.has(new URL(origin).hostname)) return json({ ok: false }, 403);
  const text = await request.text();
  if (text.length > 1024) return json({ ok: false }, 413);
  let body;
  try { body = JSON.parse(text); } catch { return json({ ok: false }, 400); }
  const e = body && typeof body === 'object' ? clean(body) : null;
  if (!e) return json({ ok: false }, 400);

  const now = Math.floor(Date.now() / 1000);
  const recent = await env.DB.prepare('SELECT COUNT(*) AS n FROM events WHERE ts > ?').bind(now - 60).first();
  if (recent && recent.n >= MAX_PER_MINUTE) return json({ ok: false }, 429, { 'Retry-After': '60' });

  await env.DB.prepare(
    'INSERT INTO events (ts, clips, holders, plates, printer, nfc, sleeve, vendors) VALUES (?, ?, ?, ?, ?, ?, ?, ?)'
  ).bind(now, e.clips, e.holders, e.plates, e.printer, e.nfc, e.sleeve, e.vendors).run();
  return json({ ok: true }, 202);
}

async function stats(request, env, ctx) {
  const cache = caches.default;
  const key = new Request(new URL('/api/stats', request.url).href);
  const hit = await cache.match(key);
  if (hit) return hit;
  const row = await env.DB.prepare(
    'SELECT COUNT(*) AS batches, COALESCE(SUM(clips), 0) AS clips, COALESCE(SUM(holders), 0) AS holders FROM events'
  ).first();
  const res = json(row, 200, {
    'Cache-Control': 'public, max-age=300',
    'Access-Control-Allow-Origin': '*',
  });
  ctx.waitUntil(cache.put(key, res.clone()));
  return res;
}

export default {
  async fetch(request, env, ctx) {
    const { pathname } = new URL(request.url);
    try {
      if (pathname === '/api/stat' && request.method === 'POST') return await record(request, env);
      if (pathname === '/api/stats' && request.method === 'GET') return await stats(request, env, ctx);
    } catch (err) {
      console.error('usage counter error', String(err));
      return json({ ok: false }, 500);
    }
    return pathname.startsWith('/api/') ? json({ ok: false }, 404) : env.ASSETS.fetch(request);
  },
};
