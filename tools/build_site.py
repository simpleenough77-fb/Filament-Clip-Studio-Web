"""Prepare the published site. Run by .github/workflows/pages.yml before every deploy.

  python tools/build_site.py            # write downloads/catalog.csv and SOURCE_HASHES.json
  python tools/build_site.py --stamp    # also stamp the build badge in index.html (CI only)
  python tools/build_site.py --redirect-stub DIR HOST
                                        # write a GitHub Pages site that forwards every path to HOST

downloads/catalog.csv is the single catalog feed for the Google Sheets CSV builder, whose
Catalog tab imports it with =IMPORTDATA(). It is generated from author/Catalog.json, so the
studio and the sheet can no longer drift apart. Both generated files are git-ignored.
"""
import csv, hashlib, io, json, os, re, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG_CSV = ROOT / 'downloads' / 'catalog.csv'
HASHES = ROOT / 'SOURCE_HASHES.json'
CATALOG_HEADER = ['Manufacturer', 'Filament type', 'Color / name', 'Source', 'Swatch']
GENERATED = {'SOURCE_HASHES.json', 'downloads/catalog.csv'}


def catalog_csv_text(root=ROOT):
    products = json.loads((root / 'author' / 'Catalog.json').read_text(encoding='utf-8'))['products']
    out = io.StringIO()
    writer = csv.writer(out, lineterminator='\n')
    writer.writerow(CATALOG_HEADER)
    for p in products:
        writer.writerow([p['manufacturer'], p['filament_type'], p['color_name'], p.get('source', ''), p.get('swatch', '')])
    return out.getvalue()


def tracked_files(root=ROOT):
    try:
        names = subprocess.run(['git', 'ls-files', '-z'], cwd=root, capture_output=True, check=True).stdout.decode().split('\0')
    except (OSError, subprocess.CalledProcessError):
        names = [str(p.relative_to(root)).replace(os.sep, '/') for p in root.rglob('*') if p.is_file() and '.git' not in p.parts]
    return sorted(n for n in names if n and n not in GENERATED and not n.startswith('.github/') and (root / n).is_file())


def source_hashes(root=ROOT):
    return {n: hashlib.sha256((root / n).read_bytes()).hexdigest() for n in tracked_files(root)}


def stamp_build(root=ROOT):
    sha = (os.environ.get('GITHUB_SHA') or subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=root, capture_output=True, text=True).stdout.strip() or 'dev')[:7]
    day = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    index = root / 'index.html'
    html, count = re.subn(r'>Build [^<]*</span>', f'>Build {sha} · {day}</span>', index.read_text(encoding='utf-8'), count=1)
    if count != 1:
        sys.exit('Build badge not found in index.html')
    index.write_text(html, encoding='utf-8')
    return sha, day


REDIRECT = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Filament Clip Studio has moved</title>
<link rel="canonical" href="{host}/"><meta http-equiv="refresh" content="0; url={host}/">
<script>
// Keep the page, query and fragment: /Filament-Clip-Studio-Web/guide.html#x -> {host}/guide.html#x
var p = location.pathname.replace(/^\\/Filament-Clip-Studio-Web/i, '') || '/';
location.replace('{host}' + p + location.search + location.hash);
</script></head>
<body style="font-family:system-ui,sans-serif;background:#10191d;color:#edf3f3;padding:40px">
<p>Filament Clip Studio has moved to <a style="color:#83eac5" href="{host}/">{host}</a>.</p></body></html>
"""


def write_redirect_stub(dest, host):
    """GitHub Pages fallback: every old github.io URL forwards to the new host.

    downloads/catalog.csv is kept so copies of the Google Sheets builder made before
    the move keep loading the catalog.
    """
    dest = Path(dest); host = host.rstrip('/')
    (dest / 'downloads').mkdir(parents=True, exist_ok=True)
    page = REDIRECT.replace('{host}', host)
    for name in ('index.html', '404.html'):
        (dest / name).write_text(page, encoding='utf-8')
    (dest / '.nojekyll').write_text('', encoding='utf-8')
    (dest / 'downloads' / 'catalog.csv').write_text(catalog_csv_text(), encoding='utf-8')


def main():
    if '--redirect-stub' in sys.argv:
        i = sys.argv.index('--redirect-stub')
        write_redirect_stub(sys.argv[i + 1], sys.argv[i + 2])
        print('Wrote GitHub Pages redirect to', sys.argv[i + 2])
        return
    CATALOG_CSV.parent.mkdir(exist_ok=True)
    CATALOG_CSV.write_text(catalog_csv_text(), encoding='utf-8')
    hashes = source_hashes()
    HASHES.write_text(json.dumps(hashes, indent=2) + '\n', encoding='utf-8')
    print(f'catalog.csv: {len(catalog_csv_text().splitlines()) - 1} products; SOURCE_HASHES.json: {len(hashes)} files')
    if '--stamp' in sys.argv:
        print('Stamped build %s · %s' % stamp_build())


if __name__ == '__main__':
    main()
