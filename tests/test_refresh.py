"""Offline checks for tools/refresh_catalog.py (no network: a fake fetcher serves canned store pages).
  python tests/test_refresh.py      (needs Pillow, like the tool itself)
"""
import copy, io, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import refresh_catalog as rc  # noqa: E402
from PIL import Image  # noqa: E402

CATALOG = json.loads((ROOT / 'author' / 'Catalog.json').read_text())
# Start from a catalog that has no PETG Matte yet, whatever the real file lists today.
CATALOG['products'] = [p for p in CATALOG['products'] if not (p['manufacturer'] == 'Bambu Lab' and p['filament_type'] == 'PETG Matte')]


def png(rgb):
    b = io.BytesIO(); Image.new('RGBA', (20, 20), rgb + (255,)).save(b, 'PNG'); return b.getvalue()


def bambu_page(variants, swatches):
    group = {'@type': 'ProductGroup', 'name': 'Test', 'url': 'x', 'hasVariant': [
        {'name': f'{t} - {n}({c}) / Refill / 1kg', 'sku': s, 'offers': {'availability': 'https://schema.org/InStock'}} for t, n, c, s in variants]}
    lis = ''.join(f'<li value="{n}({c})"><img src="https://store.bblcdn.com/{c}.png"></li>' for t, n, c, s in variants if c in swatches)
    return f'<script type="application/ld+json">{json.dumps(group)}</script>{lis}'


class Fake:
    def __init__(self, files): self.files = files
    def text(self, url):
        if url not in self.files: raise rc.FetchError(url)
        return self.files[url]
    def bytes(self, url):
        if url not in self.files: raise rc.FetchError(url)
        return self.files[url]


def bambu_world(extra_variants=(), swatches=(35100,)):
    base = [('PETG Matte', 'White', '35100', '1'), *extra_variants]
    sw = {str(c) for c in swatches}
    files = {f'{rc.BAMBU_HOST}/sitemap_products_1.xml': '<loc>https://x/products/petg-matte</loc>',
             f'{rc.BAMBU_HOST}/products/petg-matte': bambu_page(base, sw), 'https://store.bblcdn.com/35100.png': png((255, 255, 255))}
    for _, _, c, _ in extra_variants: files[f'https://store.bblcdn.com/{c}.png'] = png((10, 20, 30))
    return files


def run_bambu(files, products=None):
    data = {'version': '3.7', 'updated': '2026-01-01', 'note': 'n', 'products': copy.deepcopy(products if products is not None else CATALOG['products'])}
    state = {}
    rep = rc.run(data, state, Fake(files), '2026-10-22', ['Bambu Lab'])
    return data, rep


def test_new_bambu_line_is_added_with_sampled_swatch():
    data, rep = run_bambu(bambu_world([('PETG Matte', 'Black', '35101', '2')], [35100, 35101]))
    new = [p for p in data['products'] if p['manufacturer'] == 'Bambu Lab' and p['filament_type'] == 'PETG Matte']
    assert {p['color_name'] for p in new} == {'White', 'Black'}, new
    assert {p['swatch'] for p in new} == {'#FFFFFF', '#0A141E'}
    assert data['version'] == '3.8' and data['updated'] == '2026-10-22'
    assert rep.added and not [e for e in rep.errors if 'petg-matte' in e]  # other pages are not served by the fake store


def test_second_run_adds_nothing():
    data, _ = run_bambu(bambu_world([('PETG Matte', 'Black', '35101', '2')], [35100, 35101]))
    again, rep = run_bambu(bambu_world([('PETG Matte', 'Black', '35101', '2')], [35100, 35101]), data['products'])
    assert len(again['products']) == len(data['products']) and not rep.added


def test_existing_entries_are_untouched_and_ids_unique():
    data, _ = run_bambu(bambu_world([('PETG Matte', 'Black', '35101', '2')], [35100, 35101]))
    assert data['products'][:0] == [] and all(p in data['products'] for p in CATALOG['products'])
    ids = [p['id'] for p in data['products']]
    assert len(ids) == len(set(ids))


def test_color_without_a_swatch_goes_to_review_not_catalog():
    data, rep = run_bambu(bambu_world([('PETG Matte', 'Zorp Zorp', '35999', '3')], [35100]))
    assert not any(p['color_name'] == 'Zorp Zorp' for p in data['products'])
    assert any('Zorp Zorp' in r for r in rep.review), rep.review


def test_unsafe_names_are_not_added():
    data, rep = run_bambu(bambu_world([('PETG Matte', 'Bad"Name', '35998', '4')], [35100, 35998]))
    assert not any('Bad' in p['color_name'] for p in data['products']) and rep.review


def test_one_vendor_failing_does_not_stop_the_others():
    data = {'version': '3.7', 'updated': 'x', 'note': 'n', 'products': copy.deepcopy(CATALOG['products'])}
    rep = rc.run(data, {}, Fake({}), '2026-10-22', ['Bambu Lab', 'Amolen'])
    assert len(rep.errors) == 2 and rep.failed_all and len(data['products']) == len(CATALOG['products'])


def test_swatch_sampling_reproduces_a_known_color():
    assert rc.sample_swatch(png((190, 225, 148))) == '#BEE194'


if __name__ == '__main__':
    failures = 0
    for name, fn in list(globals().items()):
        if name.startswith('test_') and callable(fn):
            try:
                fn(); print('PASS', name)
            except Exception as e:  # noqa: BLE001
                failures += 1; print('FAIL', name, '-', repr(e))
    sys.exit(1 if failures else 0)
