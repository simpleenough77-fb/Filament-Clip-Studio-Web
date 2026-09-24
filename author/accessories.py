"""Clip holders and mounting templates added to a batch by device count.

One template per device type in use; holders per device (AMS HT: one one-post,
AMS 2 Pro: one four-post, Creality SpacePi X4: two two-post). Parts print flat
as supplied, on their own plates after the clip plates.
"""
import math, struct
from pathlib import Path
from placement import GAP, MARGIN, pack

ROOT = Path(__file__).resolve().parent.parent
FILES = ROOT / 'downloads' / 'accessories'
ROLE = 'Shared black body filament - choose in slicer'
COLOR = '#000000'
MAX_PER_DEVICE = 20

DEVICES = {
    'ams_ht': dict(label='Bambu Lab AMS HT', template=('AMS HT mounting template', 'AMS_HT_template.stl'),
                   holders=[('One-post holder', 'One_post_holder.stl', 1)]),
    'ams_2_pro': dict(label='Bambu Lab AMS 2 Pro', template=('AMS 2 Pro mounting template', 'AMS_2_Pro_template.stl'),
                      holders=[('Four-post holder', 'Quad_post_holder.stl', 1)]),
    'spacepi_x4': dict(label='Creality SpacePi X4', template=('Creality SpacePi X4 mounting template', 'Creality_SpacePi_X4_template.stl'),
                       holders=[('Two-post holder', 'Dual_post_holder.stl', 2)]),
}
_MESHES = {}


def validate_devices(raw):
    raw = raw or {}
    if not isinstance(raw, dict):
        raise ValueError('Device counts must be a list of device types and numbers.')
    clean = {}
    for key, value in raw.items():
        if key not in DEVICES:
            raise ValueError('Unknown device type for holders: ' + str(key))
        if isinstance(value, bool) or str(value).strip() not in [str(n) for n in range(MAX_PER_DEVICE + 1)]:
            raise ValueError(f'Enter 0 to {MAX_PER_DEVICE} units for each device type.')
        if int(value):
            clean[key] = int(value)
    return clean


def parts_list(devices):
    """[(name, file, quantity)] in a stable order, merging identical parts."""
    wanted = {}
    for key in DEVICES:
        n = devices.get(key, 0)
        if not n:
            continue
        d = DEVICES[key]
        name, file = d['template']
        wanted.setdefault(file, [name, 0])[1] += 1
        for hname, hfile, per in d['holders']:
            wanted.setdefault(hfile, [hname, 0])[1] += per * n
    return [(name, file, qty) for file, (name, qty) in wanted.items()]


def load_mesh(file):
    """Binary STL -> (verts, faces), centred on X/Y with the base at Z=0."""
    if file not in _MESHES:
        raw = (FILES / file).read_bytes()
        count = struct.unpack_from('<I', raw, 80)[0]
        if len(raw) != 84 + 50 * count:
            raise ValueError('Damaged accessory file ' + file)
        verts, faces, lookup = [], [], {}
        for t in range(count):
            v = struct.unpack_from('<9f', raw, 84 + 50 * t + 12)
            face = []
            for i in (0, 3, 6):
                pt = tuple(round(c, 6) for c in v[i:i + 3])
                if pt not in lookup:
                    lookup[pt] = len(verts); verts.append(pt)
                face.append(lookup[pt])
            if len(set(face)) == 3:
                faces.append(face)
        lo = [min(p[k] for p in verts) for k in range(3)]
        hi = [max(p[k] for p in verts) for k in range(3)]
        cx, cy = (lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2
        _MESHES[file] = ([(x - cx, y - cy, z - lo[2]) for x, y, z in verts], faces, hi[0] - lo[0], hi[1] - lo[1])
    return _MESHES[file]


def rotated(verts, degrees):
    r = math.radians(degrees); c, s = math.cos(r), math.sin(r)
    return [(x * c - y * s, x * s + y * c, z) for x, y, z in verts]


def bbox(verts):
    xs = [p[0] for p in verts]; ys = [p[1] for p in verts]
    return max(xs) - min(xs), max(ys) - min(ys)


def area_of(printer):
    r = printer['single']
    return [r[0] + MARGIN, r[1] + MARGIN, r[2] - MARGIN, r[3] - MARGIN]


def fits_axis(w, h, area):
    W, H = area[2] - area[0], area[3] - area[1]
    return (w + GAP <= W + 1e-6 and h + GAP <= H + 1e-6) or (h + GAP <= W + 1e-6 and w + GAP <= H + 1e-6)


def plan(devices, printer, first_variant):
    """Return (variants, plates). Variant indices start at first_variant.

    Parts that only fit diagonally get a mesh rotated to the first angle that
    fits and a plate of their own.
    """
    variants, plates, loose = [], [], []
    area = area_of(printer)
    for name, file, qty in parts_list(devices):
        verts, faces, w, h = load_mesh(file)
        check = dict(lines=[name], filament_roles=[ROLE, ROLE], body_color=COLOR, text_color=COLOR, accessory=True)
        if fits_axis(w, h, area):
            index = first_variant + len(variants)
            variants.append(dict(check=check, parts=[(name, (verts, faces))]))
            loose += [dict(variant=index, w=w, h=h, accessory=name) for _ in range(qty)]
            continue
        for tenth in range(5, 900, 5):
            turned = rotated(verts, tenth / 10)
            bw, bh = bbox(turned)
            if bw + GAP <= area[2] - area[0] + 1e-6 and bh + GAP <= area[3] - area[1] + 1e-6:
                break
        else:
            raise ValueError(f'The {name} ({w:.0f} x {h:.0f} mm) does not fit the {printer["id"]} plate. '
                             'Choose a printer with a larger bed, or print it separately from the Holders & mounting templates page.')
        index = first_variant + len(variants)
        variants.append(dict(check=check, parts=[(name, (turned, faces))]))
        cx, cy = (area[0] + area[2]) / 2, (area[1] + area[3]) / 2
        for _ in range(qty):
            plates.append(dict(items=[dict(variant=index, w=bw, h=bh, x=cx - bw / 2, y=cy - bh / 2, rotated=False, accessory=name)],
                               tower=None, area=area, name='Holders and templates'))
    if loose:
        for p in pack(loose, printer, two_color=False):
            p['name'] = 'Holders and templates'
            plates.append(p)
    return variants, plates


def summary(devices):
    return [dict(name=name, quantity=qty) for name, _, qty in parts_list(devices)]
