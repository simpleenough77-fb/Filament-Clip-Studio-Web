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


if __name__ == '__main__':
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith('test_') and callable(fn):
            try:
                fn(); print('PASS', name)
            except Exception as e:  # noqa: BLE001
                failures += 1; print('FAIL', name, '-', e)
    sys.exit(1 if failures else 0)
