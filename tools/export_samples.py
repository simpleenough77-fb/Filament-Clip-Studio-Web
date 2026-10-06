"""Generate sample batches with the real generator, for opening or slicing in each slicer.

Needs the OpenSCAD desktop app (the browser build uses a WebAssembly copy instead).

  python3 tools/export_samples.py --out OUTDIR [--printer bambu-350x320] [--slicer orca] [--sleeve yes|no]
                                  [--style part|cut] [--devices ams_2_pro=1,ams_ht=1]
                                  [--rows 'Bambu Lab:PETG-HF:Blue:2,Cookiecad:PLA:Dark Magic:2']

Writes OUTDIR/<name>.3mf and prints one line per file. Pass --name to choose the file name.
"""
import argparse, asyncio, os, platform, subprocess, sys, tempfile, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'author'))
import generator as g  # noqa: E402

DEFAULT_ROWS = 'Bambu Lab:PETG-HF:Blue:2,Cookiecad:PLA:Dark Magic:2'


def openscad_command():
    exe = os.environ.get('OPENSCAD') or '/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD'
    if not Path(exe).exists():
        sys.exit('OpenSCAD not found. Install it or set OPENSCAD to its executable.')
    # The desktop build used for the validated meshes is Intel-only on Apple Silicon.
    return ['arch', '-x86_64', exe] if platform.system() == 'Darwin' and platform.machine() == 'arm64' else [exe]


def make_native(cmd):
    async def native(code, target):
        code = code.replace('"/author/', '"' + str(ROOT / 'author') + '/')
        source = target.with_suffix('.scad')
        source.write_text(code)
        args = ['--export-format', 'binstl'] if target.suffix == '.stl' else []
        for attempt in range(3):
            p = subprocess.run([*cmd, '--backend=Manifold', '--enable=textmetrics', *args, '-o', str(target), str(source)],
                               capture_output=True, text=True, encoding='utf-8')
            # The Intel OpenSCAD build occasionally crashes at start-up (a setlocale race under Rosetta); a retry is enough.
            if p.returncode >= 0 or attempt == 2:
                break
        assert p.returncode == 0 and 'ERROR:' not in p.stderr, p.stderr
        return p.stderr
    return native


def parse_rows(text):
    rows = []
    for item in text.split(','):
        maker, kind, color, qty = item.rsplit(':', 3)
        product = next(p['id'] for p in g.CATALOG if (p['manufacturer'], p['filament_type'], p['color_name']) == (maker, kind, color))
        rows.append(dict(product=product, quantity=int(qty)))
    return rows


def parse_devices(text):
    return {k: int(v) for k, v in (pair.split('=') for pair in text.split(','))} if text else {}


async def build(out, name, rows, settings):
    review = await g.preflight(dict(rows=rows, settings=settings))
    result = await g.generate(review['key'], True)
    archive = g.GENERATED / Path(result['download']).name
    with zipfile.ZipFile(archive) as z:
        names = [n for n in z.namelist() if n.endswith('.3mf')]
        if names == ['Filament_Labels.3mf']:
            target = out / (name + '.3mf')
            target.write_bytes(z.read(names[0]))
        else:  # PrusaSlicer: one project per plate
            for n in names:
                (out / n.replace('Filament_Labels', name)).write_bytes(z.read(n))
            target = out / names[0].replace('Filament_Labels', name)
    return target, result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--name', default=None)
    ap.add_argument('--printer', default='bambu-350x320', help='printer group id from author/Printers.json')
    ap.add_argument('--slicer', default='', help='bambu_studio, orca, creality_print, elegoo, anycubic, snapmaker_orca or prusa (default: the brand\'s own)')
    ap.add_argument('--multicolor', default='yes', choices=['no', 'yes'])
    ap.add_argument('--sleeve', default='no', choices=['no', 'yes'])
    ap.add_argument('--style', default='part', choices=['part', 'cut'])
    ap.add_argument('--nfc', default='no', choices=['no', 'yes'])
    ap.add_argument('--devices', default='')
    ap.add_argument('--rows', default=DEFAULT_ROWS)
    a = ap.parse_args()
    out = Path(a.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix='clip-samples-'))
    g.CACHE = work / 'cache'
    g.GENERATED = work / 'generated'
    g.CACHE.mkdir()
    g.GENERATED.mkdir()
    g.run_scad = make_native(openscad_command())
    settings = dict(printer=a.printer, slicer=a.slicer, multicolor=a.multicolor, holder_sleeve=a.sleeve, style=a.style, nfc=a.nfc, devices=parse_devices(a.devices))
    name = a.name or f'{a.printer}-{a.slicer or "default"}-{"sleeve" if a.sleeve == "yes" else "standing"}'
    target, result = asyncio.run(build(out, name, parse_rows(a.rows), settings))
    print(f'{target}  plates={result["plates"]} clips={result["total"]}')


if __name__ == '__main__':
    main()
