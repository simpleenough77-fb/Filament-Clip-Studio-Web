// Checks what the feedback endpoint accepts, normalizes and stores, and that the browser code never renders visitor text.
// Run: node tests/test_feedback.mjs
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { cleanFeedback, normalizeComment, publicItem, moderate, TAGS, MAX_COMMENT } from '../worker/feedback.js';
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

// ---- moderation ----------------------------------------------------------------------------------------------
const m = (s) => moderate(normalizeComment(s));
for (const fine of ['Great clips, fit my Sunlu spools perfectly', 'Great class assembly, as expected', 'Prints at 220 60 0.4 0.2 1.75 worked',
  'PLA Basic, e.g. Bambu Lab Matte, v1.0 works', '3.5mm and 1.75mm filament, 10.5 hours', 'Scunthorpe and Dickens are fine', 'as expected', 'Assembly and class were easy', 'bass guitar', 'AMAZING!!!!!!!!!!!!', 'Love the AMS HT holder, thanks!'])
  assert.equal(m(fine), null, fine);
for (const link of ['Visit www.cheap-filament.com now', 'see https://evil.example/x', 'check example dot com', 'mail me at bob@example.com', 'bob (at) example (dot) com',
  'call 404-555-1234 today', 'follow @spammer please', 'cheap.xyz is great', 'ＨＴＴＰ：//evil.example'])
  assert.equal(m(link), 'link', link);
for (const rude of ['what an asshole', 'you ass', 'this is sh1t', 'You f u c k i n g suck', 'fuuuuck', 'F.U.C.K', 'the dick clip', 'what an a$$hole'])
  assert.equal(m(rude), 'language', rude);
for (const spam of ['BUY CRYPTO NOW', 'best casino bonus', 'free money here', 'aaaaaaaaaaaa', 'SEO services for you'])
  assert.equal(m(spam), 'spam', spam);
assert.equal(m('THIS IS AMAZING I LOVE IT SO MUCH'), 'caps');
assert.equal(m(null), null); assert.equal(moderate(''), null);

// ---- request handling with a fake D1 -------------------------------------------------------------------------
const rows = [];
let counts = { minute: 0, day: 0 };
let duplicateOf = null; // what the duplicate-comment lookup returns
let stored = [];   // what the list queries return
let totals = { n: 0, average: 0, r1: 0, r2: 0, r3: 0, r4: 0, r5: 0 };
const listSql = [];
const env = {
  DB: {
    prepare: (sql) => {
      const stmt = {
        first: async () => { if (/COUNT\(\*\) AS n/.test(sql)) { listSql.push(sql); return totals; } if (/^SELECT 1 AS dup/.test(sql)) return duplicateOf; return counts; },
        all: async () => { listSql.push(sql); return { results: stored }; },
        run: async () => { assert.match(sql, /^INSERT INTO feedback \(ts, source, rating, tags, comment, flag, hidden\) VALUES \(\?, \?, \?, \?, \?, \?, \?\)$/); },
      };
      stmt.bind = (...args) => ({ ...stmt, run: async () => { await stmt.run(); rows.push(args); } });
      return stmt;
    },
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

assert.equal(rows[0][5], null); assert.equal(rows[0][6], 0);                     // clean comment: published, not hidden
for (const [text, flag, hidden] of [['Visit www.evil.example', 'link', 0], ['what a sh1t print', 'language', 0], ['LOVE IT SO MUCH I REALLY DO', 'caps', 0], ['BUY CRYPTO NOW', 'spam', 1]]) {
  res = await post({ ...ok, comment: text });
  assert.equal(res.status, 202, text); assert.deepEqual(await res.json(), { ok: true }); // same answer, so a spammer learns nothing
  assert.deepEqual(rows.at(-1).slice(5), [flag, hidden], text);
  assert.equal(rows.at(-1)[2], 4, 'the rating is stored either way');
}
duplicateOf = { dup: 1 };
res = await post({ ...ok, comment: 'Same words as before' }); assert.equal(res.status, 202);
assert.deepEqual(rows.at(-1).slice(5), ['duplicate', 0]);
res = await post({ ...ok, comment: null }); assert.deepEqual(rows.at(-1).slice(4), [null, null, 0], 'no comment: nothing to flag or look up');
duplicateOf = null;
rows.length = 1;

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

// Only POST (store) and GET (the public list) exist; nothing can edit or delete, and no CORS headers are ever sent.
for (const method of ['PUT', 'PATCH', 'DELETE', 'OPTIONS']) {
  res = await worker.fetch(new Request('https://filamentclip.com/api/feedback', { method, headers: { Origin: 'https://evil.example' } }), env, ctx);
  assert.equal(res.status, 404, method); assert.equal(res.headers.get('Access-Control-Allow-Origin'), null, method);
}
res = await post(ok, { origin: 'https://evil.example' });
assert.equal(res.headers.get('Access-Control-Allow-Origin'), null);

// ---- the public list -----------------------------------------------------------------------------------------
const get = (headers = {}) => worker.fetch(new Request('https://filamentclip.com/api/feedback?x=1', { headers }), env, ctx);
res = await get();                                                                   // empty table
assert.equal(res.status, 200); assert.deepEqual(await res.json(), { count: 0, average: 0, counts: [0, 0, 0, 0, 0], items: [] });
totals = { n: 3, average: 4.3333, r1: 0, r2: 0, r3: 1, r4: 0, r5: 2 };
const evil = '<img src=x onerror=alert(1)><script>alert(2)</script>＜b＞bold＜/b＞\u202Ehidden\u200B  text\n=cmd';
stored = [
  { ts: 1792000000, rating: 5, tags: '["fit","easy"]', comment: evil },                  // a row someone edited by hand
  { ts: 1791990000, rating: 3, tags: '["<script>","fit","fit",7,"constructor"]', comment: null },
  { ts: 1791980000, rating: 9, tags: '[]', comment: 'bad rating row is dropped' },
  { ts: 1791970000, rating: 5, tags: 'not json', comment: "'=1+1", reply: '<b>Thanks</b>\u202E for the reminder', reply_ts: 1792100000 },
];
res = await get({ Origin: 'https://evil.example' });
assert.equal(res.status, 200);
assert.equal(res.headers.get('Access-Control-Allow-Origin'), null);                   // only the site's own pages can read it
assert.equal(res.headers.get('Content-Type'), 'application/json');
assert.equal(res.headers.get('X-Content-Type-Options'), 'nosniff');
assert.equal(res.headers.get('Cache-Control'), 'public, max-age=60');
const list = await res.json();
assert.deepEqual(list.counts, [0, 0, 1, 0, 2]); assert.equal(list.count, 3); assert.equal(list.average, 4.3);
assert.equal(list.items.length, 3, 'rows with an impossible rating are dropped');
assert.deepEqual(list.items[0], { date: '2026-10-14', rating: 5, tags: ['easy', 'fit'], comment: normalizeComment(evil) });
assert.ok(!/[<>]/.test(JSON.stringify(list)), 'no angle bracket can come out of the list');
assert.ok(!/[\u0000-\u001F\u200B-\u200F\u202A-\u202E]/.test(list.items[0].comment));
assert.deepEqual(list.items[1].tags, ['fit']); assert.equal(list.items[1].comment, null);
assert.deepEqual(list.items[2].tags, []); assert.equal(list.items[2].comment, "'=1+1"); // already-defused text is stable
assert.equal(list.items[2].reply, 'bThanks/b for the reminder'); assert.equal(list.items[2].reply_date, '2026-10-15'); assert.ok(!('reply' in list.items[0]));
assert.deepEqual(Object.keys(list.items[0]).sort(), ['comment', 'date', 'rating', 'tags']); // no id, no time of day, no source
assert.equal(publicItem({ ts: 0, rating: 4, tags: '[]', comment: normalizeComment('=SUM(1)') }).comment, "'=SUM(1)"); // idempotent
assert.equal(publicItem(null), null); assert.equal(publicItem({ rating: 'x' }), null);
for (const sql of listSql.slice(-2)) assert.match(sql, /WHERE hidden = 0/, 'hidden rows must never be listed or counted');
assert.match(listSql.at(-1), /CASE WHEN flag IS NULL THEN comment END AS comment/, 'flagged comments are withheld from the public list');
assert.match(listSql.at(-1), /LIMIT \?$/);
stored = []; totals = { n: 0, average: 0, r1: 0, r2: 0, r3: 0, r4: 0, r5: 0 };

// A database failure returns a generic error and leaks nothing about the visitor's text.
const failing = { ...env, DB: { prepare: () => ({ bind: () => ({ first: async () => { throw new Error('d1 down'); } }) }) } };
res = await worker.fetch(new Request('https://filamentclip.com/api/feedback', { method: 'POST', headers: { Origin: 'https://filamentclip.com', 'Content-Type': 'application/json' }, body: JSON.stringify({ ...ok, comment: 'secret words' }) }), failing, ctx);
assert.equal(res.status, 500); assert.equal(await res.text(), '{"ok":false}');

// ---- the browser code ----------------------------------------------------------------------------------------
const client = readFileSync(new URL('../feedback.js', import.meta.url), 'utf8');
const listClient = readFileSync(new URL('../feedback_list.js', import.meta.url), 'utf8');
for (const code of [client, listClient]) for (const banned of ['innerHTML', 'outerHTML', 'insertAdjacentHTML', 'document.write', 'eval(', 'new Function', 'srcdoc', 'DOMParser', 'createContextualFragment'])
  assert.ok(!code.includes(banned), 'feedback code must not use ' + banned);
const clientTags = JSON.parse(/const TAGS = (\[\[.*?\]\]);/.exec(client)[1]);
assert.deepEqual(clientTags.map(t => t[0]).sort(), [...TAGS].sort(), 'topic ids in feedback.js and worker/feedback.js must match');
for (const [, label] of clientTags) assert.ok(label.length < 40);
assert.ok(client.includes("fetch('/api/feedback'") && !/credentials\s*:\s*['"]include/.test(client), 'same-origin, no credentials');
assert.ok(listClient.includes("fetch('/api/feedback'") && !/credentials\s*:\s*['"]include/.test(listClient));
assert.ok(!/\.(?:href|src|action)\s*=/.test(listClient), 'the list never turns visitor text into a link or resource');

console.log('feedback checks passed');
