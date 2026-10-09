"""NFC tag pockets: shallow recesses that hold a round NFC sticker flush with the surface.

A pocket is the tag diameter plus CLEARANCE wide and DEPTH deep (default: a 25 mm tag in a
25.4 x 0.5 mm pocket). Where it goes:

* Clip without a holder sleeve: the back of the faceplate, beside the filament tunnel on the
  left (-X) side. It is cut into the clip body in OpenSCAD together with the label. The space
  between the tunnel and the leg is narrower than a 25 mm tag on Cookiecad and Amolen clips,
  so there the circle is trimmed flat on the tunnel and leg sides (trim the sticker to match).
* Clip with a holder sleeve: the centre of the flat top of the sleeve plate. Added to the 3MF
  as a negative part, so the owner-tested sleeve mesh and its support painting stay untouched.
* Holders: the underside, 4 mm back from the front edge, centred under each post. Also a
  negative part.

Measurements come from the shipped meshes; tests/test_quick.py re-checks them against the files.
"""
import math
from print_geometry import PROFILES

NAME = 'NFC tag pocket'      # part name in the 3MF; batch_export treats it as a negative part
DEFAULT_TAG = 25.0
MIN_TAG = 10.0
MAX_TAG = 25.0
CLEARANCE = 0.4              # pocket diameter = tag diameter + this
DEPTH = 0.5                  # recess depth; the sticker sits flush or a little proud
WALL = 0.4                   # minimum wall kept beside a trimmed pocket
SEGMENTS = 96

PLATE_TOP = 3.6              # back of the faceplate (front face is z = 0)
TUNNEL_HALF = 1.73           # half-width of the tunnel's footprint on the back of the faceplate
LEG_INNER = {name: p['leg_inner'] for name, p in PROFILES.items()}    # |x| of each leg's inner face
SLEEVE_TOP = {name: p['sleeve_top'] for name, p in PROFILES.items() if p['sleeve']}  # top of the sleeve plate
PLATE = {name: p['plate'] for name, p in PROFILES.items()}               # back of the faceplate, per vendor

FRONT_MARGIN = 4.0           # holders: wall left between the pocket and the front edge
# Holder post centres (mm from the left edge of the STL / of each half), measured from the shipped files.
HOLDER_POSTS = {
    'One_post_holder.stl': [38.54],
    'Dual_post_holder.stl': [38.54, 117.96],
    'Quad_post_holder.stl': [40.89, 120.32, 199.74, 279.17],
}
SPLIT_POSTS = {'Split_4_post_holder.stl': [[42.95, 122.38], [40.90, 120.33]]}   # one list per half, in file order


def validate_tag(value):
    try:
        tag = float(value)
    except (TypeError, ValueError):
        raise ValueError(f'NFC tag diameter must be a number from {MIN_TAG:g} to {MAX_TAG:g} mm.')
    if isinstance(value, bool) or not MIN_TAG <= tag <= MAX_TAG:
        raise ValueError(f'NFC tag diameter must be from {MIN_TAG:g} to {MAX_TAG:g} mm.')
    return tag


def diameter(tag):
    return tag + CLEARANCE


def sleeveless_strip(profile):
    """(low, high) x range on the back of the faceplate, left of the tunnel, that a pocket may occupy."""
    return -(LEG_INNER[profile] - WALL), -(TUNNEL_HALF + WALL)


def is_trimmed(profile, tag):
    """True when the pocket must be trimmed flat to fit between the tunnel and the leg."""
    lo, hi = sleeveless_strip(profile)
    return hi - lo < diameter(tag) - 1e-9


def sleeveless_cutter_scad(profile, tag):
    """OpenSCAD cutter (design frame: front face z = 0) for a clip without a sleeve."""
    d = diameter(tag)
    lo, hi = sleeveless_strip(profile)
    cx = (lo + hi) / 2
    cylinder = f'translate([{cx:.4f},0,{PLATE[profile] - DEPTH:.4f}]) cylinder(d={d:.4f},h={DEPTH + 0.01:.4f},$fn={SEGMENTS});'
    if hi - lo < d - 1e-9:
        return f'intersection(){{{cylinder} translate([{lo:.4f},-20,0]) cube([{hi - lo:.4f},40,10]);}}'
    return cylinder


def cylinder_mesh(centers, z0, z1, d, segments=SEGMENTS):
    """Closed, outward-facing cylinders (one per centre) as (vertices, faces) in a single mesh."""
    r = d / 2
    verts, faces = [], []
    for cx, cy in centers:
        base = len(verts)
        ring = [(cx + r * math.cos(2 * math.pi * i / segments), cy + r * math.sin(2 * math.pi * i / segments)) for i in range(segments)]
        verts += [(x, y, z0) for x, y in ring] + [(x, y, z1) for x, y in ring] + [(cx, cy, z0), (cx, cy, z1)]
        bottom, top, cb, ct = base, base + segments, base + 2 * segments, base + 2 * segments + 1
        for i in range(segments):
            j = (i + 1) % segments
            faces += [[bottom + i, bottom + j, top + j], [bottom + i, top + j, top + i],
                      [cb, bottom + j, bottom + i], [ct, top + i, top + j]]
    return verts, faces


def sleeve_pocket_mesh(profile, tag):
    """Negative-part cutter for the top of the sleeve plate, centred (design frame)."""
    top = SLEEVE_TOP[profile]
    return cylinder_mesh([(0.0, 0.0)], top - DEPTH, top + 0.2, diameter(tag))


def holder_pocket_centers(file, width, height, tag, piece=None):
    """Pocket centres in a holder mesh's own frame (centred on X/Y, as accessories.load_mesh returns it).

    `piece` is the index of the half for the split holder. Front edge of every holder is its low-Y side."""
    posts = SPLIT_POSTS[file][piece] if file in SPLIT_POSTS else HOLDER_POSTS[file]
    return [(x - width / 2, -height / 2 + FRONT_MARGIN + diameter(tag) / 2) for x in posts]


def holder_pocket_mesh(centers, tag):
    """Negative-part cutter for the underside of a holder (z = 0 is the base)."""
    return cylinder_mesh(centers, 0.0, DEPTH, diameter(tag))
