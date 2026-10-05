"""One-off: wrote author/Printers.json (one entry per brand and bed size) from the earlier per-model list.
Kept as the record of where the bed sizes come from; edit Printers.json directly from now on.

Bambu Lab groups keep a real stock profile (author/Printer_Settings) because Bambu Studio projects
carry the full printer preset. Every other brand uses the generic bed-only configuration, so a group
only needs its bed. Bed sizes come from the vendors' machine profiles bundled with Orca Slicer 2.4.
"""
import json, sys
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / 'author' / 'Printers.json'
OLD = json.loads(OUT.read_text()) if OUT.exists() else {}

def sized(w, d): return f'{w:g} x {d:g} mm'

groups = []
def bambu(gid, models, source, **kw):
    p = OLD[source]
    g = dict(id=gid, brand='Bambu Lab', models=models, bed=p['bed'], usable=p['usable'], single=p['single'],
             exclusions=p['exclusions'], settings=p['settings'], dual=p['dual'], multi=True,
             source='Installed Bambu Studio 2.08.02.61 stock 0.4 mm profiles')
    g.update(kw); groups.append(g)

bambu('bambu-180x180', 'A1 mini', 'A1 mini')
# P1S carries the 18 x 28 mm purge-chute keep-out, which keeps the layout valid for all of these.
bambu('bambu-256x256', 'A1, P1P, P1S, P2S, X1, X1 Carbon, X1E', 'P1S')
bambu('bambu-256x256-dual', 'X2D', 'X2D')
bambu('bambu-330x320', 'A2L', 'A2L')
bambu('bambu-330x320-dual', 'H2C', 'H2C')
bambu('bambu-340x320', 'H2S', 'H2S')
bambu('bambu-350x320', 'H2D, H2D Pro', 'H2D')

OTHER = {
 'Creality': [(220, 215, 250, 'K2 SE'), (220, 220, 250, 'Ender-3 V3 / V3 SE / V3 KE, Ender-3 V2, Ender-5, K1'), (250, 250, 250, ''), (260, 260, 260, 'Hi, K2, SPARKX i7'),
              (300, 300, 300, 'K1 Max, K2 Pro, CR-10 V2 / V3, Ender-3 V3 Plus'), (350, 350, 350, 'Ender-5 Plus, K2 Plus'), (400, 400, 400, '')],
 'Elegoo': [(230, 230, 250, 'Neptune 3 Pro, Neptune 4, Neptune 4 Pro'), (256, 256, 256, 'Centauri, Centauri 2, Centauri Carbon, Centauri Carbon 2'), (325, 325, 320, 'Neptune 3 Plus, Neptune 4 Plus')],
 'Anycubic': [(220, 220, 250, 'Kobra, Kobra 2, Kobra 2 Neo, Kobra 2 Pro, Kobra Neo'), (250, 250, 250, 'Kobra S1'), (255, 255, 260, 'Kobra 3'), (260, 260, 260, 'Kobra X'),
              (300, 300, 300, ''), (350, 350, 350, 'Kobra S1 Max')],
 'Prusa': [(180, 180, 180, 'MINI'), (250, 210, 220, 'MK3.5, MK3S+, MK4, MK4S'), (250, 220, 270, 'CORE One'), (300, 300, 330, 'CORE One L'), (360, 360, 360, 'XL')],
}
for brand, rows in OTHER.items():
    for w, d, h, models in rows:
        # Heights are conservative: only clips, holders and templates are printed, all far lower than any of these.
        groups.append(dict(id=f'{brand.lower()}-{w}x{d}', brand=brand, models=models, bed=[float(w), float(d), float(h)], usable=[0.0, 0.0, float(w), float(d)],
                           single=[0.0, 0.0, float(w), float(d)], exclusions=[], settings=None, dual=False, multi=False,
                           source='Bed size from the vendor machine profiles bundled with Orca Slicer 2.4'))
for g in groups:
    w, d, h = g['bed']
    g['label'] = f"{sized(w, d)}" + (f" · {g['models']}" if g['models'] else ' · other models with this bed')
    g['bed_label'] = sized(w, d)
data = {g['id']: g for g in groups}
# Printer names saved in earlier drafts keep working.
ALIASES = {'H2D': 'bambu-350x320', 'H2D Pro': 'bambu-350x320', 'H2S': 'bambu-340x320', 'H2C': 'bambu-330x320-dual', 'X2D': 'bambu-256x256-dual',
           'X1 Carbon': 'bambu-256x256', 'X1E': 'bambu-256x256', 'X1': 'bambu-256x256', 'P2S': 'bambu-256x256', 'P1S': 'bambu-256x256', 'P1P': 'bambu-256x256',
           'A1': 'bambu-256x256', 'A1 mini': 'bambu-180x180', 'A2L': 'bambu-330x320'}
OUT.write_text(json.dumps(data, indent=1))
(OUT.parent / 'Printer_Aliases.json').write_text(json.dumps(ALIASES, indent=1))
sys.path.insert(0, str(OUT.parent))
from slicers import SLICERS
(OUT.parent / 'Slicers.json').write_text(json.dumps({k: dict(label=v['label'], family=v['family']) for k, v in SLICERS.items()}, indent=1))
print(len(data), 'groups')
