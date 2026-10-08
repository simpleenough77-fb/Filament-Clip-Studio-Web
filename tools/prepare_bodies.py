"""Turn the owner's per-vendor clip STLs into the bodies the studio ships (author/<vendor>.stl and <vendor>_sleeve.stl).

    python tools/prepare_bodies.py "/path/to/Clip STLs"          # needs numpy and manifold3d (pip install manifold3d numpy)

Each vendor has two source files, "<Vendor> clip only.stl" and "<Vendor> with sleeve.stl" (Jayo's is "Jayo with Sleeve.stl").
The owner models every clip face down: front (label) face on z = 0, legs rising from the back. This script
  * merges the separate overlapping shells a CAD export leaves behind into one watertight solid (union),
  * drops label text baked into the face (shells no taller than the 0.6 mm label inlay; the Amolen files contain some),
  * centres the body on X/Y using the clip-only bounds, so the sleeve version lines up with it,
  * writes a binary STL and records source and result hashes in author/Bodies_Provenance.json.
"""
import hashlib, json, struct, sys
from pathlib import Path
import numpy as np
import manifold3d as m3d

ROOT = Path(__file__).resolve().parent.parent
AUTHOR = ROOT / 'author'
VENDORS = {'bambu': 'Bambu Lab', 'cookiecad': 'Cookiecad', 'amolen': 'Amolen', 'sunlu': 'Sunlu', 'jayo': 'Jayo',
           'polymaker': 'Polymaker', 'panchroma': 'Panchroma', 'inland': 'Inland'}
LABEL_INLAY = 0.61


def load(path):
    raw = Path(path).read_bytes()
    n = struct.unpack_from('<I', raw, 80)[0]
    if 84 + 50 * n != len(raw):
        raise ValueError(f'{path}: binary STL expected')
    rec = np.frombuffer(raw, dtype=np.dtype([('n', '<3f4'), ('v', '<9f4'), ('a', '<u2')]), count=n, offset=84)
    return rec['v'].reshape(-1, 3, 3).astype(float)


def shells(tris):
    key = lambda v: tuple(np.round(v, 4))
    parent = {}
    def find(x):
        while parent.setdefault(x, x) != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for t in tris:
        a, b, c = (key(v) for v in t)
        parent[find(b)] = find(a)
        parent[find(c)] = find(a)
    groups = {}
    for t in tris:
        groups.setdefault(find(key(t[0])), []).append(t)
    return [np.array(g) for g in groups.values()]


def solid(tris):
    verts, inv = np.unique(np.round(tris.reshape(-1, 3), 4), axis=0, return_inverse=True)
    faces = inv.reshape(-1, 3).astype(np.uint32)
    faces = faces[(faces[:, 0] != faces[:, 1]) & (faces[:, 1] != faces[:, 2]) & (faces[:, 0] != faces[:, 2])]
    m = m3d.Manifold(m3d.Mesh(vert_properties=verts.astype(np.float32), tri_verts=faces))
    if m.status() != m3d.Error.NoError:
        raise ValueError(f'shell is not a closed solid: {m.status()}')
    return m


def merged(path):
    parts = shells(load(path))
    biggest = max(len(p) for p in parts)
    kept = [p for p in parts if not (len(parts) > 1 and len(p) < biggest and p[:, :, 2].max() <= LABEL_INLAY and p[:, :, 2].min() <= 1e-3)]
    u = m3d.Manifold.batch_boolean([solid(p) for p in kept], m3d.OpType.Add)
    mesh = u.to_mesh()
    return np.array(mesh.vert_properties)[:, :3].astype(float), np.array(mesh.tri_verts), len(parts) - len(kept)


def write(path, verts, faces):
    out = bytearray(b'Filament Clip Studio body (merged shells, centred on X/Y, front face at z=0)'.ljust(80, b' '))
    out += struct.pack('<I', len(faces))
    for a, b, c in faces:
        p, q, r = verts[a], verts[b], verts[c]
        n = np.cross(q - p, r - p)
        n = n / np.linalg.norm(n) if np.linalg.norm(n) > 0 else n
        out += struct.pack('<12fH', *n, *p, *q, *r, 0)
    Path(path).write_bytes(bytes(out))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main(folder):
    folder = Path(folder)
    record = {}
    for stem, vendor in VENDORS.items():
        clip = folder / f'{vendor} clip only.stl'
        sleeve = next(p for p in folder.glob('*.stl') if p.name.lower() == f'{vendor} with sleeve.stl'.lower())
        cv, cf, cdrop = merged(clip)
        centre = (cv.min(0) + cv.max(0)) / 2
        shift = np.array([centre[0], centre[1], 0.0])
        for source, name in ((clip, stem), (sleeve, stem + '_sleeve')):
            v, f, dropped = (cv, cf, cdrop) if source == clip else merged(source)
            write(AUTHOR / f'{name}.stl', v - shift, f)
            record[f'{name}.stl'] = dict(source=source.name, source_sha256=sha(source), sha256=sha(AUTHOR / f'{name}.stl'),
                                         triangles=int(len(f)), label_text_shells_dropped=dropped)
            print(f'{name}.stl: {len(f)} triangles, {dropped} label shells dropped')
    (AUTHOR / 'Bodies_Provenance.json').write_text(json.dumps(record, indent=2) + '\n')


if __name__ == '__main__':
    main(sys.argv[1])
