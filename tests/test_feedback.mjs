// Checks what the feedback endpoint accepts, normalizes and stores, and that the browser code never renders visitor text.
// Run: node tests/test_feedback.mjs
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { cleanFeedback, normalizeComment, TAGS, MAX_COMMENT } from '../worker/feedback.js';
import worker from '../worker/stat.js';

// ---- normalization -------------------------------------------------------------------------------------------
const n = normalizeComment;
assert.equal(n('  Love   it\n\n  so   much\t!  '), 'Love it so much !');            // whitespace collapsed and trimmed
assert.equal(n('<script>alert(1)</script>hi'), 'scriptalert(1)/scripthi');           // angle brackets never survive
assert.equal(n('<img src=x onerror=alert(1)>'), 'img src=x onerror=alert(1)');
assert.equal(n('＜script＞alert(1)＜/script＞'), 'scriptalert(1)/script');            // full-width look-alikes folded by NFKC, then removed
assert.equal(n('a​b‮c\u0000d\u0007e﻿f'), 'abcdef');                    // zero-width, bidi override, NUL, BEL, BOM
assert.equal(n('x y z'), 'x y z');
assert.equal(n('ｆｕｌｌ ｗｉｄｔｈ'), 'full width');                                  // compatibility characters
assert.equal(n('é'), 'é');                                                 // composed form
assert.equal(n('=HYPERLINK("http://evil","x")'), '\'=HYPERLINK("http://evil","x")');  // spreadsheet formula defused
assert.equal(n('+1 to this'), "'+1 to this");
assert.equal(n('-2 clips'), "'-2 clips");
assert.equal(n('@SUM(A1)'), "'@SUM(A1)");
assert.equal(n('＝cmd|x'), "'=cmd|x");                                                  // full-width "=" is caught after NFKC
assert.equal(n('fits well = great'), 'fits well = great');                            // only a leading character matters
assert.equal(n(''), null); assert.equal(n('   \n\t '), null); assert.equal(n('​​'), null);
for (const bad of [undefined, null, 5, true, {}, [], ['x']]) assert.equal(n(bad), null);
const long = n('é'.repeat(5000));
assert.equal([...long].length, MAX_COMMENT);
assert.equal(n('😀'.repeat(600)).length, MAX_COMMENT * 2);                            // counted in characters, not UTF-16 units
assert.ok(!/[<>\u0000-\u001F]/.test(n('<<>>\u0001\n"quoted" & \'single\'')));
assert.equal(n('SELECT * FROM feedback; DROP TABLE feedback;--'), 'SELECT * FROM feedback; DROP TABLE feedback;--'); // stored as inert text

// ---- validation ----------------------------------------------------------------------------------------------
const ok = { rating: 4, source: 'download', tags: ['fit', 'easy'], comment: 'Nice' };
assert.deepEqual(cleanFeedback(ok), { rating: 4, source: 'download', tags: '["easy","fit"]', comment: 'Nice' });
assert.equal(cleanFeedback({ rating: 5, source: 'page' }).comment, null);
assert.equal(cleanFeedback({ rating: 5, source: 'page' }).tags, '[]');
for (const r of [0, 6, -1, 3.5, '4', null, undefined, NaN, Infinity, [4], {}]) assert.equal(cleanFeedback({ ...ok, rating: r }), null, 'rating ' + String(r));
for (const s of ['', 'Download', 'admin', 'download; DROP', null, 1, undefined, ['page']]) assert.equal(cleanFeedback({ ...ok, source: s }), null, 'source ' + String(s));
for (const b of [null, undefined, 'x', 5, [], [ok]]) assert.equal(cleanFeedback(b), null);
assert.equal(cleanFeedback({ ...ok, tags: ['nope', '<b>', 'fit', 'fit', 7, null, {}, "x'); DROP TABLE feedback;--"] }).tags, '["fit"]'); // unknown ids dropped, dupes folded
assert.equal(cleanFeedback({ ...ok, tags: 'fit' }).tags, '[]');
assert.equal(cleanFeedback({ ...ok, tags: [...TAGS, ...TAGS, ...TAGS] }).tags, JSON.stringify([...TAGS].sort()));
assert.deepEqual(cleanFeedback({ ...ok, website: 'http://spam.example' }), { spam: true });  // honeypot
assert.notDeepEqual(cleanFeedback({ ...ok, website: '' }), { spam: true });
const extra = cleanFeedback({ ...ok, id: 9, ts: 1, ip: '1.2.3.4', admin: true, __proto__: { x: 1 } });
assert.deepEqual(Object.keys(extra).sort(), ['comment', 'rating', 'source', 'tags']);        // unknown fields are never stored

// ---- request handling with a fake D1 -------------------------------------------------------------------------
const rows = [];
let counts = { minute: 0, day: 0 };
const env = {
  DB: {
    prepare: (sql) => ({
      bind: (...args) => ({
        first: async () => counts,
        run: async () => { assert.match(sql, /^INSERT INTO feedback \(ts, source, rating, tags, comment\) VALUES \(\?, \?, \?, \?, \?\)$/); rows.push(args); },
      }),
    }),
  },
  ASSETS: { fetch: async () => new Response('asset') },
};
const ctx = { waitUntil() {} };
const post = (body, { origin = 'https://filamentclip.com', type = 'application/json', raw = false, headers = {} } = {}) =>
  worker.fetch(new Request('https://filamentclip.com/api/feedback', {
    method: 'POST',
    headers: { ...(origin ? { Origin: origin } : {}), ...(type ? { 'Content-Type': type } : {}), ...headers },
    body: raw ? body : JSON.stringify(body),
  }), env, ctx);

let res = await post({ ...ok, comment: '<b onclick=x>Great</b> =1+1' });
assert.equal(res.status, 202); assert.deepEqual(await res.json(), { ok: true });
assert.equal(res.headers.get('X-Content-Type-Options'), 'nosniff');
assert.equal(rows.length, 1);
const [ts, source, rating, tags, comment] = rows[0];
assert.ok(Math.abs(ts - Date.now() / 1000) < 5); assert.equal(source, 'download'); assert.equal(rating, 4);
assert.equal(tags, '["easy","fit"]'); assert.equal(comment, 'b onclick=xGreat/b =1+1');

res = await post({ ...ok, website: 'bot' });                  // honeypot looks successful but stores nothing
assert.equal(res.status, 202); assert.equal(rows.length, 1);

const before = rows.length;
assert.equal((await post(ok, { origin: 'https://evil.example' })).status, 403);   // wrong site
assert.equal((await post(ok, { origin: 'https://filamentclip.com.evil.example' })).status, 403);
assert.equal((await post(ok, { origin: null })).status, 403);                     // no Origin header
assert.equal((await post(ok, { origin: 'null' })).status, 403);                   // sandboxed iframe / file: origins
assert.equal((await post(ok, { origin: 'not a url' })).status, 403);
assert.equal((await post(ok, { type: 'text/plain' })).status, 415);               // a plain cross-site form post is refused
assert.equal((await post(ok, { type: 'application/x-www-form-urlencoded' })).status, 415);
assert.equal((await post(ok, { type: null })).status, 415);
assert.equal((await post('{not json', { raw: true })).status, 400);
assert.equal((await post('null', { raw: true })).status, 400);
assert.equal((await post('[]', { raw: true })).status, 400);
assert.equal((await post({ ...ok, rating: 9 })).status, 400);
assert.equal((await post({ ...ok, comment: 'x'.repeat(5000) })).status, 413);       // bigger than 4 KB is rejected unread
assert.equal((await post(JSON.stringify(ok), { raw: true, headers: { 'Content-Length': '999999' } })).status, 413);
assert.equal(rows.length, before, 'rejected requests must not write');

counts = { minute: 60, day: 60 };                                                   // global minute breaker
res = await post(ok); assert.equal(res.status, 429); assert.equal(res.headers.get('Retry-After'), '60');
counts = { minute: 1, day: 1000 };                                                  // global daily breaker
assert.equal((await post(ok)).status, 429);
counts = { minute: null, day: 0 };                                                  // empty table: SUM() is NULL
assert.equal((await post(ok)).status, 202);
assert.equal(rows.length, before + 1);

// There is no way to read feedback back, and no CORS headers are ever sent.
for (const method of ['GET', 'PUT', 'DELETE', 'OPTIONS']) {
  res = await worker.fetch(new Request('https://filamentclip.com/api/feedback', { method, headers: { Origin: 'https://evil.example' } }), env, ctx);
  assert.equal(res.status, 404, method); assert.equal(res.headers.get('Access-Control-Allow-Origin'), null, method);
}
res = await post(ok, { origin: 'https://evil.example' });
assert.equal(res.headers.get('Access-Control-Allow-Origin'), null);

// A database failure returns a generic error and leaks nothing about the visitor's text.
const failing = { ...env, DB: { prepare: () => ({ bind: () => ({ first: async () => { throw new Error('d1 down'); } }) }) } };
res = await worker.fetch(new Request('https://filamentclip.com/api/feedback', { method: 'POST', headers: { Origin: 'https://filamentclip.com', 'Content-Type': 'application/json' }, body: JSON.stringify({ ...ok, comment: 'secret words' }) }), failing, ctx);
assert.equal(res.status, 500); assert.equal(await res.text(), '{"ok":false}');

// ---- the browser code ----------------------------------------------------------------------------------------
const client = readFileSync(new URL('../feedback.js', import.meta.url), 'utf8');
for (const banned of ['innerHTML', 'outerHTML', 'insertAdjacentHTML', 'document.write', 'eval(', 'new Function', 'srcdoc', 'DOMParser', 'createContextualFragment'])
  assert.ok(!client.includes(banned), 'feedback.js must not use ' + banned);
const clientTags = JSON.parse(/const TAGS = (\[\[.*?\]\]);/.exec(client)[1]);
assert.deepEqual(clientTags.map(t => t[0]).sort(), [...TAGS].sort(), 'topic ids in feedback.js and worker/feedback.js must match');
for (const [, label] of clientTags) assert.ok(label.length < 40);
assert.ok(client.includes("fetch('/api/feedback'") && !/credentials\s*:\s*['"]include/.test(client), 'same-origin, no credentials');

console.log('feedback checks passed');
