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
    for printer in ('X1 Carbon', 'A1 mini'):
        try:
            accessories.plan({'ams_2_pro': 1}, g.PRINTERS[printer], 0)
        except ValueError as e:
            assert 'does not fit' in str(e)
        else:
            raise AssertionError('four-post holder must be rejected on ' + printer)
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

if __name__ == '__main__':
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith('test_') and callable(fn):
            try:
                fn(); print('PASS', name)
            except Exception as e:  # noqa: BLE001
                failures += 1; print('FAIL', name, '-', e)
    sys.exit(1 if failures else 0)
