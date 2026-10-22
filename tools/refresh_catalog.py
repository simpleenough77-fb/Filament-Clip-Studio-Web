#!/usr/bin/env python3
"""Refresh author/Catalog.json from the manufacturers' own stores.

  python tools/refresh_catalog.py                  # check: print a report, change nothing
  python tools/refresh_catalog.py --apply          # add what it safely can; writes author/Catalog.json and author/Refresh_State.json
  python tools/refresh_catalog.py --report FILE    # also write the report (markdown) to FILE
  python tools/refresh_catalog.py --vendor Amolen  # only these vendors (repeatable)

It only ever ADDS. Existing entries are never removed, renamed or reordered, because saved batches refer to their ids.

  Added automatically   Bambu Lab (store pages), Amolen, Geeetech, Polymaker, Panchroma (Shopify product feeds):
                        new colors on products the catalog already lists, and new Bambu filament lines.
  Reported for review   anything else that changed: new products or new variants at Sunlu, Jayo, Protopasta, and new
                        product lines at the automatic vendors (naming a new line is a human decision).
  Not readable by script  Cookiecad and Creality publish no product feed; Micro Center (Inland) blocks automated requests.
                        These are updated by hand.

Availability is deliberately not tracked for existing entries: stock flips daily and nothing reads it, so it would only add noise.
"""
import argparse, collections, io, json, re, sys, time, urllib.error, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
CATALOG_FILE = ROOT / 'author' / 'Catalog.json'
STATE_FILE = ROOT / 'author' / 'Refresh_State.json'
USER_AGENT = 'FilamentClipStudio-catalog-refresh (+https://filamentclip.com)'
NOTE_SENTENCE = (" The catalog is refreshed every day from the manufacturers' stores (tools/refresh_catalog.py): new colors are added and nothing "
                 'is ever removed, so saved batches keep working. Cookiecad, Creality and Inland cannot be read automatically and are updated by hand.')

BAMBU = 'Bambu Lab'
BAMBU_HOST = 'https://us.store.bambulab.com'
# Handles that can be filament lines; accessories, multi-packs and parts are skipped by name.
BAMBU_FILAMENT = re.compile(r'^(pla|petg|pet|abs|asa|pc|pa\d*|paht|ppa|pps|tpu|pva|support)(-|$)')
BAMBU_NOT_A_LINE = re.compile(r'(pack|set|bundle|kit|trial|lithophane|module|roller|assembly|sample|combo)')

UNREADABLE = {
    'Cookiecad': 'its store publishes no product feed',
    'Creality': 'its store publishes no product feed',
    'Inland': 'Micro Center blocks automated requests',
}


def keep_amolen(o): return o.get('delivery option', '') == 'U.S. to U.S.'
def keep_geeetech(o): return o.get('ship from', '') == 'US'
def keep_polymaker(o):
    return (o.get('diameter', '1.75mm') == '1.75mm' and o.get('net weight', o.get('weight', '1kg')) == '1kg'
            and not o.get('type', '').casefold().startswith('old'))

# Automatic Shopify vendors: which feed, which variants are the spool the catalog lists, how entry ids are built.
AUTO_SHOPIFY = {
    'Amolen': dict(host='www.amolen.com', keep=keep_amolen, ids='type-color', source_name='color'),
    'Geeetech': dict(host='www.geeetech.com', keep=keep_geeetech, ids='sku', source_name='color'),
    'Polymaker': dict(host='shop.polymaker.com', keep=keep_polymaker, ids='sku', source_name='title'),
    'Panchroma': dict(host='shop.polymaker.com', keep=keep_polymaker, ids='sku', source_name='title'),
}
# Shopify vendors whose option layouts vary too much to add from automatically: new products and new variants are reported.
WATCH_SHOPIFY = {'Sunlu': 'store.sunlu.com', 'Jayo': 'store.jayo3d.com', 'Protopasta': 'www.protopasta.com'}
FEED_VENDORS = {'Amolen': ['Amolen'], 'Geeetech': ['Geeetech'], 'Polymaker': ['Polymaker', 'Panchroma'],
                'Sunlu': ['Sunlu'], 'Jayo': ['Jayo'], 'Protopasta': ['Protopasta Cardboard', 'Protopasta Plastic']}
FEED_HOSTS = {'Amolen': 'www.amolen.com', 'Geeetech': 'www.geeetech.com', 'Polymaker': 'shop.polymaker.com', **WATCH_SHOPIFY}


class FetchError(Exception):
    pass


class Fetcher:
    """Plain HTTPS GET with a polite User-Agent, a short retry, and a per-run cache."""
    def __init__(self):
        self.cache = {}

    def _get(self, url):
        last = None
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT, 'Accept': '*/*'})
                with urllib.request.urlopen(req, timeout=40) as r:
                    return r.read()
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                last = e
                time.sleep(2 * (attempt + 1))
        raise FetchError(f'{url}: {last}')

    def bytes(self, url):
        if url not in self.cache:
            self.cache[url] = self._get(url)
        return self.cache[url]

    def text(self, url):
        return self.bytes(url).decode('utf-8', 'replace')


# ---- small helpers -------------------------------------------------------------------------------------------------
def norm(s):
    return re.sub(r'[^a-z0-9]+', ' ', str(s).casefold()).strip()

def slug(s):
    return re.sub(r'[^a-z0-9]+', '-', str(s).casefold()).strip('-')

def handle_of(url):
    return urlparse(url).path.rstrip('/').rsplit('/', 1)[-1]

def safe_name(s):
    # The catalog test refuses backslashes and quotes in names (they break the OpenSCAD label); also no control characters.
    return bool(s) and s == s.strip() and not re.search(r'[\\"\x00-\x1f<>]', s)

def known_colors(entries):
    out = set()
    for e in entries:
        out.add(norm(e['color_name']))
        out.update(norm(a[2]) for a in e.get('label_aliases', []) if len(a) > 2)
        if e.get('source_color_name'):
            out.add(norm(re.sub(r'\s*\(\d+\)\s*$', '', e['source_color_name'].split(' / ')[0])))
    return out


class Report:
    def __init__(self):
        self.added, self.review, self.errors = [], [], []

    def markdown(self, today, applied):
        n = sum(len(a['colors']) for a in self.added)
        out = [f'# Catalog refresh {today}', '']
        out.append(f'## {"Added" if applied else "Would add"}: {n} color{"" if n == 1 else "s"}')
        out += [f"- **{a['vendor']} {a['type']}** ({len(a['colors'])}): " + ', '.join(a['colors']) + (f"  \n  needs a swatch check: {', '.join(a['placeholders'])}" if a['placeholders'] else '') for a in self.added] or ['- Nothing new.']
        out += ['', '## Needs a human look']
        out += [f'- {r}' for r in self.review] or ['- Nothing.']
        out += ['', '## Not readable by script (update by hand)']
        out += [f'- {v}: {why}' for v, why in UNREADABLE.items()]
        if self.errors:
            out += ['', '## Errors (these vendors were skipped this time)'] + [f'- {e}' for e in self.errors]
        return '\n'.join(out) + '\n'


# ---- swatches ------------------------------------------------------------------------------------------------------
def sample_swatch(png_bytes):
    """Mean color of the middle 40% of a manufacturer swatch image (reproduces the hex of existing Bambu entries exactly)."""
    from PIL import Image
    im = Image.open(io.BytesIO(png_bytes)).convert('RGBA')
    w, h = im.size
    raw = im.crop((int(w * .3), int(h * .3), int(w * .7), int(h * .7))).tobytes()
    px = [(raw[i], raw[i + 1], raw[i + 2]) for i in range(0, len(raw), 4) if raw[i + 3] > 200]
    if not px:
        raise ValueError('swatch image has no opaque pixels')
    return '#%02X%02X%02X' % tuple(round(sum(p[c] for p in px) / len(px)) for c in range(3))

def guess_swatch(products, vendor, color):
    """A preview color for a color we have no swatch image for: the same name elsewhere in the catalog, else None."""
    n = norm(color)
    for scope in ([p for p in products if p['manufacturer'] == vendor], products):
        hits = collections.Counter(p['swatch'].upper() for p in scope if norm(p['color_name']) == n and not p.get('swatch_effects'))
        if hits:
            return hits.most_common(1)[0][0]
    return None


# ---- Bambu Lab -----------------------------------------------------------------------------------------------------
def parse_bambu_page(html):
    """-> dict(name, url, colors={code: dict(name, type, skus, available, swatch)}) from a Bambu store product page, or None."""
    group = None
    for m in re.finditer(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', html, re.S):
        try:
            data = json.loads(m.group(1))
        except ValueError:
            continue
        for d in (data if isinstance(data, list) else [data]):
            if isinstance(d, dict) and d.get('@type') == 'ProductGroup':
                group = d
    if not group:
        return None
    swatches = {}
    for name, url in re.findall(r'<li value="([^"]+)"[^>]*><img src="(https://store\.bblcdn\.com/[^"]+)"', html):
        swatches.setdefault(name, url)
    colors = {}
    for v in group.get('hasVariant', []):
        parts = [p.strip() for p in str(v.get('name', '')).split(' / ')]
        m = re.match(r'^(?P<type>.+?) - (?P<color>.+?)\s*\((?P<code>\d{4,6})\)$', parts[0])
        if not m:
            return None  # not the "Type - Color(code) / form / size" layout of a single filament line
        c = colors.setdefault(m['code'], dict(name=m['color'].strip(), type=m['type'].strip(), skus=[], available=False, swatch=swatches.get(f"{m['color'].strip()}({m['code']})")))
        c['skus'].append(str(v.get('sku', '')))
        c['available'] = c['available'] or str(v.get('offers', {}).get('availability', '')).endswith('InStock')
    return dict(name=str(group.get('name', '')).strip(), url=group.get('url') or '', colors=colors) if colors else None


def refresh_bambu(data, fetcher, state, report, today):
    products = data['products']
    mine = [p for p in products if p['manufacturer'] == BAMBU]
    by_handle = collections.defaultdict(list)
    for p in mine:
        by_handle[handle_of(p['source'])].append(p)
    checked = state.setdefault('Bambu Lab', {})
    sitemap = fetcher.text(f'{BAMBU_HOST}/sitemap_products_1.xml')
    handles = sorted({u.rsplit('/', 1)[-1] for u in re.findall(r'<loc>([^<]+)</loc>', sitemap) if '/products/' in u})
    new_lines = [h for h in handles if h not in by_handle and h not in checked and BAMBU_FILAMENT.match(h) and not h.startswith('filament-') and not BAMBU_NOT_A_LINE.search(h)]
    for h in new_lines + sorted(by_handle):
        existing = by_handle.get(h, [])
        try:
            page = parse_bambu_page(fetcher.text(f'{BAMBU_HOST}/products/{h}'))
        except FetchError as e:
            report.errors.append(f'Bambu Lab {h}: {e}')
            continue
        if not page:
            if not existing:
                checked[h] = 'not a single filament line'
                report.review.append(f'Bambu Lab: `{h}` looks like a filament product but not a single color line; add it by hand if it should be listed.')
            continue
        ftype = existing[0]['filament_type'] if existing else re.sub(r'\s+filament$', '', next(iter(page['colors'].values()))['type'], flags=re.I)
        if len({e['filament_type'] for e in existing}) > 1:
            report.review.append(f'Bambu Lab: `{h}` is listed under several types; skipped.')
            continue
        have = {e.get('source_color_code') for e in existing} - {None}
        names = known_colors(existing)
        triples = {(p['manufacturer'], p['filament_type'], norm(p['color_name'])) for p in products}
        profile = collections.Counter(e['spool_profile'] for e in (existing or mine)).most_common(1)[0][0]
        added, placeholders = [], []
        for code, c in page['colors'].items():
            if code in have or norm(c['name']) in names or (BAMBU, ftype, norm(c['name'])) in triples:
                continue
            if not safe_name(c['name']):
                report.review.append(f"Bambu Lab {ftype}: color name {c['name']!r} has characters the labels cannot print; add it by hand.")
                continue
            try:
                hexcolor = sample_swatch(fetcher.bytes(c['swatch'])) if c['swatch'] else None
            except (FetchError, ValueError, OSError) as e:
                hexcolor = None
                report.errors.append(f"Bambu Lab {ftype} {c['name']}: swatch image: {e}")
            method = 'Approximate colors sampled from manufacturer swatch image'
            if not hexcolor:
                hexcolor = guess_swatch(products, BAMBU, c['name'])
                method = 'Approximate color from the color name; no manufacturer swatch image was available'
                if not hexcolor:
                    report.review.append(f"Bambu Lab {ftype}: new color “{c['name']}” has no swatch; add it by hand with a color.")
                    continue
            ident, n = f"bambu-{slug(ftype)}-{slug(c['name'])}", 2
            taken = {p['id'] for p in products}
            while ident in taken:
                ident, n = f"bambu-{slug(ftype)}-{slug(c['name'])}-{n}", n + 1
            entry = dict(id=ident, manufacturer=BAMBU, filament_type=ftype, color_name=c['name'], spool_profile=profile,
                         source=f'{BAMBU_HOST}/products/{h}', source_date=today, source_color_name=f"{c['name']}({code})",
                         source_color_code=code, source_sku_ids=c['skus'])
            if c['swatch']:
                entry['swatch_source'] = c['swatch']
            entry.update(available_at_refresh=c['available'], swatch_effects=[], swatch=hexcolor, preview_palette=[hexcolor],
                         swatch_method=method, swatch_description=f"{c['name']} — approximate manufacturer swatch")
            products.append(entry)
            added.append(c['name'])
        if added:
            report.added.append(dict(vendor=BAMBU, type=ftype, colors=added, placeholders=placeholders))
        if not existing:
            checked[h] = 'added'


# ---- Shopify vendors ---------------------------------------------------------------------------------------------
def shopify_products(fetcher, host):
    out = []
    for page in range(1, 11):
        items = json.loads(fetcher.text(f'https://{host}/products.json?limit=250&page={page}')).get('products', [])
        out += items
        if len(items) < 250:
            break
    return out

def option_map(product, variant):
    return {o['name'].strip().casefold(): (variant.get(f'option{i + 1}') or '').strip() for i, o in enumerate(product['options'])}

def snapshot(products):
    return {p['handle']: len(p['variants']) for p in products}


def refresh_feed(feed, data, fetcher, state, report, today, wanted):
    """One Shopify feed: add new colors for the automatic vendors, and report new products and new variants for everyone."""
    host = FEED_HOSTS[feed]
    products = data['products']
    live = shopify_products(fetcher, host)
    by_handle = {p['handle']: p for p in live}
    tracked = collections.defaultdict(lambda: collections.defaultdict(list))   # vendor -> handle -> entries
    for e in products:
        if e['manufacturer'] in FEED_VENDORS[feed] and urlparse(e['source']).netloc.endswith(host.replace('www.', '')):
            tracked[e['manufacturer']][handle_of(e['source'])].append(e)

    for vendor, handles in tracked.items():
        cfg = AUTO_SHOPIFY.get(vendor)
        if not cfg or vendor not in wanted:
            continue
        triples = {(p['manufacturer'], p['filament_type'], norm(p['color_name'])) for p in products}
        for h, entries in sorted(handles.items()):
            product = by_handle.get(h)
            if not product:
                continue
            types = {e['filament_type'] for e in entries}
            names = [o['name'].strip().casefold() for o in product['options']]
            color_opt = next((i for i, n in enumerate(names) if n in ('color', 'colour')), None)
            if len(types) != 1 or color_opt is None:
                report.review.append(f'{vendor}: `{h}` cannot be read automatically ({"several types" if len(types) != 1 else "no Color option"}).')
                continue
            ftype = next(iter(types))
            known = known_colors(entries)
            profile = collections.Counter(e['spool_profile'] for e in entries).most_common(1)[0][0]
            weight = entries[0].get('spool_weight_g')
            added, placeholders, seen = [], [], set()
            for v in product['variants']:
                if not cfg['keep'](option_map(product, v)):
                    continue
                color = (v.get(f'option{color_opt + 1}') or '').strip()
                key = norm(color)
                if not color or key in known or key in seen or (vendor, ftype, key) in triples:
                    continue
                seen.add(key)
                if not safe_name(color):
                    report.review.append(f'{vendor} {ftype}: color name {color!r} has characters the labels cannot print; add it by hand.')
                    continue
                hexcolor = guess_swatch(products, vendor, color)
                method = 'Approximate color from the color name (same name elsewhere in the catalog)'
                if not hexcolor:
                    report.review.append(f'{vendor} {ftype}: new color “{color}” has no known swatch; add it by hand with a color.')
                    continue
                sku = (v.get('sku') or '').strip()
                ident = f'{slug(vendor)}-{slug(sku)}' if cfg['ids'] == 'sku' and sku else f'{slug(vendor)}-{slug(ftype)}-{slug(color)}'
                taken, n = {p['id'] for p in products}, 2
                base = ident
                while ident in taken:
                    ident, n = f'{base}-{n}', n + 1
                entry = dict(id=ident, manufacturer=vendor, filament_type=ftype, color_name=color, spool_profile=profile)
                if weight:
                    entry['spool_weight_g'] = weight
                entry.update(source=entries[0]['source'], source_title=product.get('title', ''), source_date=today,
                             source_color_name=v.get('title', color) if cfg['source_name'] == 'title' else color)
                if sku:
                    entry['source_sku'] = sku
                if v.get('id'):
                    entry['source_variant_id'] = v['id']
                entry.update(swatch=hexcolor, preview_palette=[hexcolor], swatch_method=method, available_at_refresh=bool(v.get('available', True)))
                if not entry['source_title']:
                    del entry['source_title']
                products.append(entry)
                added.append(color)
            if added:
                report.added.append(dict(vendor=vendor, type=ftype, colors=added, placeholders=placeholders))

    # New products and new variants, for every vendor on this feed (the state remembers what was already seen).
    now = snapshot(live)
    before = state.get(feed)
    if before is not None:
        listed = {h for hs in tracked.values() for h in hs}
        for h in sorted(set(now) - set(before)):
            report.review.append(f"{feed} store: new product “{by_handle[h].get('title', h)}” (`{h}`); add it to the catalog by hand if it is a filament we support.")
        for h in sorted(listed & set(now) & set(before)):
            if now[h] > before[h]:
                vendor = next(v for v, hs in tracked.items() if h in hs)
                if vendor in AUTO_SHOPIFY and vendor in wanted:
                    continue  # already looked at above
                report.review.append(f"{vendor}: “{by_handle[h].get('title', h)}” (`{h}`) has new variants ({before[h]} → {now[h]}); check for new colors.")
    state[feed] = now


# ---- apply ---------------------------------------------------------------------------------------------------------
def insert_entries(data, before_count):
    """New entries were appended to the end; move each to the end of its vendor's block so the file stays grouped by vendor."""
    products, new = data['products'][:before_count], data['products'][before_count:]
    for e in new:
        last = max((i for i, p in enumerate(products) if p['manufacturer'] == e['manufacturer']), default=len(products) - 1)
        same_type = [i for i, p in enumerate(products) if p['manufacturer'] == e['manufacturer'] and p['filament_type'] == e['filament_type']]
        products.insert((max(same_type) if same_type else last) + 1, e)
    data['products'] = products


def run(data, state, fetcher, today, vendors=None):
    """Compute the refresh in memory. Returns the Report; `data` and `state` are updated in place."""
    report = Report()
    count = len(data['products'])
    wanted = set(vendors) if vendors else set(AUTO_SHOPIFY) | {BAMBU} | set(WATCH_SHOPIFY)
    feeds_state = state.setdefault('feeds', {})
    steps = []
    if BAMBU in wanted:
        steps.append((BAMBU, lambda: refresh_bambu(data, fetcher, feeds_state, report, today)))
    for feed, vs in FEED_VENDORS.items():
        if wanted & set(vs) or (feed in wanted):
            steps.append((feed, lambda feed=feed: refresh_feed(feed, data, fetcher, feeds_state, report, today, wanted)))
    failed = 0
    for name, step in steps:
        try:
            step()
        except (FetchError, ValueError, KeyError, TypeError) as e:
            failed += 1
            report.errors.append(f'{name}: {type(e).__name__}: {e}')
    insert_entries(data, count)
    report.failed_all = bool(steps) and failed == len(steps)
    added = len(data['products']) - count
    if added:
        major, minor = data.get('version', '1.0').split('.')[:2]
        data['version'] = f'{major}.{int(minor) + 1}'
        data['updated'] = today
        if NOTE_SENTENCE.strip() not in data.get('note', ''):
            data['note'] = data.get('note', '').rstrip() + NOTE_SENTENCE
    state['updated'] = today
    return report


def main(argv=None, fetcher=None, today=None, catalog_file=CATALOG_FILE, state_file=STATE_FILE):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--apply', action='store_true', help='write the catalog and the state file')
    ap.add_argument('--report', help='also write the markdown report here')
    ap.add_argument('--vendor', action='append', help='only this vendor or feed (repeatable)')
    args = ap.parse_args(argv)
    today = today or datetime.now(timezone.utc).strftime('%Y-%m-%d')
    data = json.loads(Path(catalog_file).read_text(encoding='utf-8'))
    state = json.loads(Path(state_file).read_text(encoding='utf-8')) if Path(state_file).is_file() else {}
    report = run(data, state, fetcher or Fetcher(), today, args.vendor)
    text = report.markdown(today, args.apply)
    print(text)
    if args.report:
        Path(args.report).write_text(text, encoding='utf-8')
    if args.apply:
        Path(catalog_file).write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
        Path(state_file).write_text(json.dumps(state, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    return 1 if report.failed_all else 0


if __name__ == '__main__':
    sys.exit(main())
