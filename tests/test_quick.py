"""Fast checks that need no OpenSCAD. Run on every push by .github/workflows/pages.yml.

  python tests/test_quick.py        (or: python -m pytest tests/test_quick.py)

The geometry tests (test_standing_exports.py, test_sleeve_label_face.py) still need a local
OpenSCAD install and are run by hand before accepting geometry changes.
"""
import csv, io, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'author'))
sys.path.insert(0, str(ROOT / 'tools'))
import generator as g  # noqa: E402
import build_site  # noqa: E402

REQUIRED = ['manufacturer', 'filament_type', 'color_name', 'quantity']


def test_catalog_integrity():
    products = g.CATALOG
    assert len(products) > 0
    ids = [p['id'] for p in products]
    assert len(ids) == len(set(ids)), 'duplicate product ids'
    triples = [(p['manufacturer'], p['filament_type'], p['color_name']) for p in products]
    assert len(triples) == len(set(triples)), 'duplicate manufacturer/type/color rows'
    for p in products:
        for field in REQUIRED[:3]:
            assert p[field].strip() == p[field] and p[field], (p['id'], field)
        assert re.fullmatch(r'#[0-9A-Fa-f]{6}', p['swatch']), (p['id'], p['swatch'])


def test_json_files_parse_and_assets_exist():
    for path in list((ROOT / 'author').rglob('*.json')) + [ROOT / 'assets.json']:
        json.loads(path.read_text(encoding='utf-8'))
    for name in json.loads((ROOT / 'assets.json').read_text()):
        assert (ROOT / name).is_file(), f'assets.json lists missing file {name}'


def test_csv_import_matches_browser_regression():
    # Same records as qa.html: rows 3 (unknown combination) and 5 (quantity 0) are skipped.
    text = ('manufacturer,filament_type,color_name,quantity\nBambu Lab,PETG-HF,Blue,2\n'
            'Unknown,PLA,Nope,1\nCookiecad,PLA,Dark Magic,3\nBambu Lab,PETG-HF,Blue,0\n')
    result = g.import_csv(text)
    assert result['imported'] == 2 and result['total'] == 5
    assert [r['row'] for r in result['skipped']] == [3, 5]


def test_csv_import_limits_and_headers():
    over = g.import_csv('manufacturer,filament_type,color_name,quantity\nBambu Lab,PETG-HF,Blue,60\nBambu Lab,PETG-HF,Blue,60\n')
    assert over['total'] == 60 and len(over['skipped']) == 1
    # Extra columns (e.g. a Status column) and a byte-order mark are accepted.
    extra = g.import_csv('﻿manufacturer,filament_type,color_name,quantity,Status\nCookiecad,PLA,Dark Magic,1,OK\n')
    assert extra['imported'] == 1
    try:
        g.import_csv('maker,type,color,qty\nx,y,z,1\n')
    except ValueError:
        pass
    else:
        raise AssertionError('wrong headers must be rejected')


def test_catalog_csv_feed_matches_catalog():
    rows = list(csv.reader(io.StringIO(build_site.catalog_csv_text())))
    assert rows[0] == build_site.CATALOG_HEADER
    assert [tuple(r[:3]) for r in rows[1:]] == [(p['manufacturer'], p['filament_type'], p['color_name']) for p in g.CATALOG]
    # Every feed row must round-trip through the studio's own CSV import.
    text = 'manufacturer,filament_type,color_name,quantity\n' + ''.join(
        ','.join('"%s"' % v.replace('"', '""') for v in r[:3]) + ',1\n' for r in rows[1:])
    unmatched = [s for s in g.import_csv(text, capacity=10**6)['skipped'] if 'combination' in s['reason']]
    assert not unmatched, unmatched[:3]


def test_source_hashes_cover_tracked_files():
    hashes = build_site.source_hashes()
    assert 'index.html' in hashes and 'author/Catalog.json' in hashes
    assert not any(k.startswith('.github/') or k in build_site.GENERATED for k in hashes)


def test_accessories_manifest_matches_stl_files():
    import struct
    acc = json.loads((ROOT / 'downloads' / 'accessories' / 'accessories.json').read_text(encoding='utf-8'))
    ids = [i['id'] for i in acc['items']]
    assert len(ids) == len(set(ids)), 'duplicate accessory ids'
    for item in acc['items']:
        assert item['kind'] in ('holder', 'template'), item['id']
        assert item.get('pairs', '').strip(), item['id'] + ' needs pairing text for its card'
        page = (ROOT / 'accessories.html').read_text(encoding='utf-8')
        assert f'id="{item.get("mount")}"' in page, item['id'] + ' needs a mount anchor that exists on accessories.html'
        data = (ROOT / 'downloads' / 'accessories' / item['file']).read_bytes()
        count = struct.unpack('<I', data[80:84])[0]
        assert len(data) == 84 + 50 * count, f"{item['file']} is not a valid binary STL"
        lo, hi = [float('inf')] * 3, [float('-inf')] * 3
        for t in range(count):
            v = struct.unpack('<9f', data[84 + 50 * t + 12:84 + 50 * t + 48])
            for k in range(9):
                lo[k % 3] = min(lo[k % 3], v[k]); hi[k % 3] = max(hi[k % 3], v[k])
        size = [round(hi[k] - lo[k], 2) for k in range(3)]
        assert all(abs(a - b) < 0.05 for a, b in zip(size, item['size'])), (item['file'], size, item['size'])

def test_accessories_plan_and_3mf():
    import tempfile, zipfile, xml.etree.ElementTree as ET
    import accessories
    from batch_export import write_batch
    devices = accessories.validate_devices({'ams_ht': '2', 'ams_2_pro': 1, 'spacepi_x4': 1})
    names = {a['name']: a['quantity'] for a in accessories.summary(devices)}
    assert names == {'AMS HT mounting template': 1, 'One-post holder': 2, 'AMS 2 Pro mounting template': 1,
                     'Four-post holder': 1, 'Creality SpacePi X4 mounting template': 1, 'Two-post holder': 2}
    for printer in ('H2D', 'H2S', 'A2L'):
        variants, plates = accessories.plan(devices, g.PRINTERS[printer], 3)
        assert sum(len(p['items']) for p in plates) == 8, printer
        for p in plates:
            x0, y0, x1, y1 = p['area']
            for i in p['items']:
                assert x0 - 1e-6 <= i['x'] and i['x'] + i['w'] <= x1 + 1e-6 and y0 - 1e-6 <= i['y'] and i['y'] + i['h'] <= y1 + 1e-6
    for printer in ('X1 Carbon', 'P1S', 'A1 mini'):
        variants_s, plates_s = accessories.plan({'ams_2_pro': 1}, g.PRINTERS[printer], 0)
        names_s = [v['check']['lines'][0] for v in variants_s]
        assert 'Four-post holder' not in names_s and sum('Split four-post holder' in n for n in names_s) == 2, (printer, names_s)
        assert accessories.summary({'ams_2_pro': 1}, g.PRINTERS[printer])[1]['name'] == 'Split four-post holder'
        for p in plates_s:
            x0, y0, x1, y1 = p['area']
            for i in p['items']:
                assert x0 - 1e-6 <= i['x'] and i['x'] + i['w'] <= x1 + 1e-6 and y0 - 1e-6 <= i['y'] and i['y'] + i['h'] <= y1 + 1e-6
    assert [v['check']['lines'][0] for v in accessories.plan({'ams_2_pro': 1}, g.PRINTERS['H2D'], 0)[0]][1] == 'Four-post holder'
    pieces = accessories.load_pieces('Split_4_post_holder.stl')
    assert len(pieces) == 2 and all(abs(w - 163.3) < 0.5 and abs(h - 58.01) < 0.05 for _, _, w, h in pieces)
    assert accessories.plan({'ams_ht': 1}, g.PRINTERS['A1 mini'], 0)[1]
    for bad in ({'ams_ht': 21}, {'ams_ht': -1}, {'toaster': 1}, {'ams_ht': True}):
        try:
            accessories.validate_devices(bad)
        except ValueError:
            continue
        raise AssertionError(bad)
    s = g.validate(dict(rows=[dict(product=g.CATALOG[0]['id'], quantity=1)], settings=dict(printer='H2D', devices=devices)))['settings']
    variants, plates = accessories.plan(s['devices'], g.PRINTERS['H2D'], 0)
    for n, p in enumerate(plates):
        p['number'] = n + 1; p['origin'] = [n * 420, 0]
    out = Path(tempfile.mkdtemp()) / 'accessories.3mf'
    write_batch(out, variants, plates, s, g.PRINTERS['H2D'], g.AUTHOR)
    with zipfile.ZipFile(out) as z:
        assert z.testzip() is None
        model = ET.fromstring(z.read('3D/3dmodel.model'))
    assert len(model.findall('.//m:build/m:item', {'m': g.NS})) == 8

def test_github_pages_redirect_stub():
    import tempfile
    out = Path(tempfile.mkdtemp())
    build_site.write_redirect_stub(out, 'https://filamentclip.com/')
    for name in ('index.html', '404.html'):
        page = (out / name).read_text()
        assert "location.replace('https://filamentclip.com' + p" in page and 'url=https://filamentclip.com/' in page
    assert (out / 'downloads' / 'catalog.csv').read_text() == build_site.catalog_csv_text()

def test_support_footer_on_public_pages():
    for name in ('index.html', 'studio.html', 'guide.html', 'accessories.html'):
        html = (ROOT / name).read_text(encoding='utf-8')
        assert html.count('class="support"') == 1, name
        assert 'href="https://ko-fi.com/clipstudio"' in html, name
        assert 'href="https://ko-fi.com/post/Provide-Development-Hardware-A5C327LDRO"' in html, name
        assert html.index('class="support"') < html.index('</main>'), name

def test_page_images_exist():
    acc = json.loads((ROOT / 'downloads' / 'accessories' / 'accessories.json').read_text(encoding='utf-8'))
    wanted = {'images/accessories/' + i['image'] for i in acc['items']}
    for name in ('index.html', 'studio.html', 'guide.html', 'accessories.html'):
        wanted |= set(re.findall(r'images/(?:photos/)?[\w.-]+\.jpg', (ROOT / name).read_text(encoding='utf-8')))
    missing = sorted(p for p in wanted if not (ROOT / p).is_file())
    assert not missing, missing
    for p in wanted:
        assert (ROOT / p).stat().st_size < 600_000, p + ' is too large for the web; resize it'

def test_front_page_and_studio():
    home = (ROOT / 'index.html').read_text(encoding='utf-8')
    studio = (ROOT / 'studio.html').read_text(encoding='utf-8')
    assert 'studio-worker' not in home and 'bridge.js' not in home, 'front page must stay light'
    assert 'bridge.js' in studio and re.search(r'>Build [^<]*</span>', studio), 'studio keeps the app and build badge'
    for name in ('index.html', 'studio.html', 'guide.html', 'accessories.html'):
        page = (ROOT / name).read_text(encoding='utf-8')
        assert 'og:image' in page and '<meta name="description"' in page, name + ' needs share metadata'
        for href in re.findall(r'href="\./([\w-]+\.html)', page):
            assert (ROOT / href).is_file(), f'{name} links to missing {href}'
    catalog_brands = {p['manufacturer'] for p in g.CATALOG}
    for brand in catalog_brands:
        assert brand in home, 'front page supported-spools list is missing ' + brand
    assert (ROOT / '.github' / 'ISSUE_TEMPLATE' / 'spool-request.yml').is_file()

def test_clip_bodies_loaded_and_clean():
    import struct
    sys.path.insert(0, str(ROOT / 'author'))
    import print_geometry
    worker = (ROOT / 'compile-worker.js').read_text(encoding='utf-8')
    for profile, spec in print_geometry.PROFILES.items():
        for name in (spec['stem'] + '.stl', spec['stem'] + '_tested_sleeve.stl'):
            # OpenSCAD in the browser can only import bodies the compile worker copies in.
            assert f"'{name}'" in worker, f'compile-worker.js does not load {name} ({profile})'
            assert (ROOT / 'author' / name).is_file(), name
    # Amolen bodies: no stray label-text shells in the bottom 0.6 mm, and the sleeve JSON matches its STL.
    def shells(path):
        raw = (ROOT / 'author' / path).read_bytes(); n = struct.unpack_from('<I', raw, 80)[0]
        tris = [struct.unpack_from('<9f', raw, 84 + 50 * i + 12) for i in range(n)]
        parent = {}
        def find(x):
            while parent.setdefault(x, x) != x:
                parent[x] = parent[parent[x]]; x = parent[x]
            return x
        key = lambda t, i: (round(t[i], 4), round(t[i + 1], 4), round(t[i + 2], 4))
        for tr in tris:
            parent[find(key(tr, 3))] = find(key(tr, 0)); parent[find(key(tr, 6))] = find(key(tr, 0))
        groups = {}
        for tr in tris:
            groups.setdefault(find(key(tr, 0)), []).append(max(tr[2], tr[5], tr[8]))
        return n, [max(z) for z in groups.values()]
    for name in ('amolen.stl', 'amolen_tested_sleeve.stl'):
        n, tops = shells(name)
        assert all(z > 0.61 for z in tops), f'{name} contains label-text shells'
    sleeve = json.loads((ROOT / 'author' / 'Amolen_Sleeve.json').read_text())
    assert len(sleeve['body']['faces']) == shells('amolen_tested_sleeve.stl')[0] == len(sleeve['body']['paint'])
    assert sum(1 for p in sleeve['body']['paint'] if p) > 0 and len(sleeve['blocker']['faces']) > 0

if __name__ == '__main__':
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith('test_') and callable(fn):
            try:
                fn(); print('PASS', name)
            except Exception as e:  # noqa: BLE001
                failures += 1; print('FAIL', name, '-', e)
    sys.exit(1 if failures else 0)
