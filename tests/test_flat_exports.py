"""End-to-end export check for every vendor's clip: flat and face down, manifold, supports, editable text, placement.

    python3 tests/test_flat_exports.py        # needs Node (runs the studio's WebAssembly OpenSCAD; see tests/scad_node.py)

Not part of the fast checks: it compiles a few hundred small OpenSCAD jobs (a couple of minutes).
"""
import sys, asyncio, json, zipfile, collections, tempfile, xml.etree.ElementTree as ET
from pathlib import Path
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'author')); sys.path.insert(0, str(root / 'tests'))
import generator as g
import scad_node
from print_geometry import PROFILES

out = Path(tempfile.mkdtemp(prefix='clip-flat-test-'))
g.CACHE = out / 'cache'; g.GENERATED = out / 'generated'; g.CACHE.mkdir(exist_ok=True); g.GENERATED.mkdir(exist_ok=True)
g.run_scad = scad_node.runner(out)

VENDORS = ['Bambu Lab', 'Cookiecad', 'Amolen', 'Sunlu', 'Jayo', 'Polymaker', 'Panchroma', 'Inland']
rows = [dict(product=next(p['id'] for p in g.CATALOG if p['manufacturer'] == m), quantity=2) for m in VENDORS]
profile_of = [g.PRODUCTS[r['product']]['spool_profile'] for r in rows]
assert len(set(profile_of)) == len(VENDORS), 'each vendor must have its own profile'
ns = {'m': 'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'}
TEXT_LINES = ['Manufacturer', 'Filament type', 'Color name']


def manifold(obj):
    edges = collections.Counter()
    for f in obj.find('m:mesh/m:triangles', ns):
        v = [int(f.get(k)) for k in ('v1', 'v2', 'v3')]
        for a, b in ((v[0], v[1]), (v[1], v[2]), (v[2], v[0])):
            edges[(a, b)] += 1
    # every directed edge is used once and has its opposite: a closed, consistently wound surface
    return all(n == 1 and edges.get((b, a)) == 1 for (a, b), n in edges.items())


def vertices(obj):
    return [tuple(float(v.get(k)) for k in 'xyz') for v in obj.find('m:mesh/m:vertices', ns)]


def bounds(vs, matrix=None):
    if matrix:
        t = [float(x) for x in matrix.split()]
        vs = [tuple(sum(v[i] * t[3 * i + j] for i in range(3)) + t[9 + j] for j in range(3)) for v in vs]
    return [(min(v[i] for v in vs), max(v[i] for v in vs)) for i in range(3)]


def check(z, sleeve, style, slicer):
    model = ET.fromstring(z.read('3D/3dmodel.model'))
    data = json.loads(z.read('Metadata/Label_Batch.json'))
    assert data['settings']['holder_sleeve'] == sleeve
    assert len(model.findall('.//m:build/m:item', ns)) == 2 * len(rows)
    objects = {o.get('id'): o for o in model.findall('m:resources/m:object', ns)}
    assemblies = [o for o in objects.values() if o.find('m:components', ns) is not None]
    assert len(assemblies) == len(rows)
    # Orca writes its slic3rpe: text records without declaring the prefix; declare it so a namespace-aware parser accepts them.
    config = ET.fromstring(z.read('Metadata/model_settings.config').replace(b'<config>', b'<config xmlns:slic3rpe="urn:slic3rpe">', 1))
    cfg_objects = config.findall('object')
    body_bounds = []
    for variant, asm in enumerate(assemblies):
        profile = profile_of[variant]; spec = PROFILES[profile]
        comps = asm.findall('m:components/m:component', ns)
        parts = cfg_objects[variant].findall('part')
        assert len(comps) == len(parts)
        body = objects[comps[0].get('objectid')]
        assert body.get('name').startswith('Clip body') and profile in body.get('name'), body.get('name')
        vs = vertices(body); b = bounds(vs)
        # flat and face down: the front face is on z = 0 and the whole clip is only as tall as its body is deep
        assert abs(b[2][0]) < 1e-3 and abs(b[2][1] - spec['size'][2]) < 2e-3, (profile, b[2])
        assert abs(b[0][1] - b[0][0] - spec['size'][0]) < 2e-3 and abs(b[1][1] - b[1][0] - spec['size'][1]) < 2e-3, (profile, b)
        assert manifold(body), f'{profile}: body is not a closed surface'
        body_bounds.append(b)
        triangles = body.findall('m:mesh/m:triangles/m:triangle', ns)
        paint = collections.Counter(t.get('paint_supports') for t in triangles if t.get('paint_supports'))
        blockers = [p for p in parts if p.get('subtype') == 'support_blocker']
        if sleeve == 'yes':
            assert paint['4'] > 0 and paint['8'] > 0, (profile, dict(paint))
            assert len(blockers) == 1
        else:
            assert not paint and not blockers
        for c, p in zip(comps[1:4], parts[1:4]):
            obj = objects[c.get('objectid')]; assert manifold(obj), f'{profile}: text part is not a closed surface'
            tb = bounds(vertices(obj), c.get('transform'))
            assert tb[2][0] > -0.011 and tb[2][1] < 0.611 + 1e-6, (profile, tb[2])
            editable = slicer in ('bambu_studio', 'orca')
            if editable:
                matrix = {m.get('key'): m.get('value') for m in p.findall('metadata')}['matrix'].split()
                t = c.get('transform').split()
                # part matrix (4x4 rows, translation last) must agree with the component transform (3x4, translation last)
                assert [float(x) for x in (matrix[0:3] + matrix[4:7] + matrix[8:11] + [matrix[3], matrix[7], matrix[11]])] == [float(x) for x in t]
                if slicer == 'bambu_studio':
                    ti = p.find('text_info')
                    assert ti is not None and ti.get('text'), f'{profile}: text is not editable'
                    assert float(ti.get('thickness')) + float(ti.get('embeded_depth')) == 0.6
                else:
                    shape = p.find('{urn:slic3rpe}shape'); text = p.find('{urn:slic3rpe}text')
                    assert shape is not None and text is not None and text.get('text'), f'{profile}: text is not editable'
                    assert float(shape.get('depth')) == 0.6 and text.get('face_name') == 'Helvetica'
                    assert 'NSFontNameAttribute' in text.get('font_descriptor') and text.get('font_descriptor_type') == 'wxFontDescriptor_MacOsX'
                    # the local mesh sits on [-0.015, depth - 0.015], as Orca builds it
                    lz = bounds(vertices(obj))[2]
                    assert abs(lz[0] + 0.015) < 2e-3 and abs(lz[1] - 0.585) < 2e-3, lz
            else:
                assert p.find('text_info') is None and p.find('{urn:slic3rpe}text') is None and c.get('transform') is None
        if slicer in ('bambu_studio', 'orca'):
            assert len([p for p in parts if p.find('text_info') is not None or p.find('{urn:slic3rpe}text') is not None]) == 3
        for oid in [c.get('objectid') for c in comps]:
            vz = bounds(vertices(objects[oid]), next((c.get('transform') for c in comps if c.get('objectid') == oid), None))[2]
            assert vz[0] > -0.011 and vz[1] < 26, 'a part sticks out of the flat print'
    for plate in data['plates']:
        for item in plate['items']:
            b = body_bounds[item['variant']]; w = b[0][1] - b[0][0]; h = b[1][1] - b[1][0]
            if item['rotated']:
                w, h = h, w
            assert w <= item['w'] + 1e-5 and h <= item['h'] + 1e-5, (profile_of[item['variant']], round(w, 4), round(h, 4), item['w'], item['h'], item['rotated'])
    return data


async def main():
    results = []
    cases = [(s, st, 'bambu_studio') for s in ('no', 'yes') for st in ('part', 'cut')] + [('yes', 'part', 'orca'), ('no', 'part', 'prusa')]
    for sleeve, style, slicer in cases:
        settings = dict(holder_sleeve=sleeve, style=style, slicer=slicer, printer='bambu-350x320' if slicer == 'bambu_studio' else g.validate(dict(rows=rows[:1], settings={}))['settings']['printer'])
        review = await g.preflight(dict(rows=rows, settings=settings))
        result = await g.generate(review['key'], True)
        archive = g.GENERATED / Path(result['download']).name
        with zipfile.ZipFile(archive) as z:
            names = z.namelist()
            if slicer == 'prusa':
                project = [n for n in names if n.endswith('.3mf')]
                assert project, names
                with zipfile.ZipFile(z.open(project[0])) as p:
                    assert p.testzip() is None and 'Metadata/Slic3r_PE_model.config' in p.namelist()
                    cfg = ET.fromstring(p.read('Metadata/Slic3r_PE_model.config').replace(b'<config>', b'<config xmlns:slic3rpe="urn:slic3rpe">', 1))
                    texts = cfg.findall('.//{urn:slic3rpe}text')
                    assert texts and len(texts) % 3 == 0, len(texts)
                    assert len(cfg.findall('.//{urn:slic3rpe}shape')) == len(texts)
            else:
                with zipfile.ZipFile(z.open('Filament_Labels.3mf')) as p:
                    assert p.testzip() is None
                    check(p, sleeve, style, slicer)
        results.append(dict(sleeve=sleeve, style=style, slicer=slicer, plates=result['plates'], status='pass'))
        print(sleeve, style, slicer, 'PASS', flush=True)
    (out / 'results.json').write_text(json.dumps(results, indent=2))

asyncio.run(main())
