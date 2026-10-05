"""PrusaSlicer project: Slic3r_PE_model.config plus a minimal Slic3r_PE.config.

PrusaSlicer stores one mesh per object and marks volumes as triangle ranges, and it places plates
(beds) by where the instances sit, so plates are laid out on the same grid as the other exporters.
"""
import io, json, zipfile
import xml.etree.ElementTree as ET
from nfc import NAME as NFC_NAME
from batch_export import safe_name

MODEL_NS = 'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'
MAX_EXTRUDERS = 5  # one MMU3 / XL toolhead set


def write_prusa(path, variants, plates, settings, printer, author):
    single = settings.get('multicolor') == 'no' and not printer.get('multi')
    palette, slotmap = [], {}

    def slot(role, color):
        if single:
            if not palette:
                palette.append((role, color))
            return 1
        key = (role, color)
        if key not in slotmap:
            slotmap[key] = len(palette) + 1
            palette.append(key)
        return slotmap[key]

    model = ET.Element('model', unit='millimeter', attrib={'xml:lang': 'en-US', 'xmlns': MODEL_NS, 'xmlns:slic3rpe': 'http://schemas.slic3r.org/3mf/2017/06'})
    for name, value in [('slic3rpe:Version3mf', '1'), ('Title', 'Filament Labels'), ('Application', 'PrusaSlicer-2.9.0')]:
        ET.SubElement(model, 'metadata', name=name).text = value
    res = ET.SubElement(model, 'resources')
    build = ET.SubElement(model, 'build')
    cfg = ET.Element('config')
    ids = []
    has_support_paint = False
    for oid, var in enumerate(variants, start=1):
        r = var['check']
        body = slot(r['filament_roles'][0], r['body_color'])
        text = body if settings['style'] == 'cut' else slot(r['filament_roles'][1], r['text_color'])
        ids.append(oid)
        obj_name = safe_name(' - '.join(r['lines']))
        oc = ET.SubElement(cfg, 'object', id=str(oid), instances_count='0')
        ET.SubElement(oc, 'metadata', type='object', key='name', value=obj_name)
        ET.SubElement(oc, 'metadata', type='object', key='extruder', value=str(body))
        obj = ET.SubElement(res, 'object', id=str(oid), type='model')
        mesh = ET.SubElement(obj, 'mesh')
        vnode = ET.SubElement(mesh, 'vertices')
        tnode = ET.SubElement(mesh, 'triangles')
        voffset = tcount = 0
        for i, (name, (verts, faces)) in enumerate(var['parts']):
            for x, y, z in verts:
                ET.SubElement(vnode, 'vertex', x=str(x), y=str(y), z=str(z))
            for fi, (a, b, c) in enumerate(faces):
                attrs = dict(v1=str(a + voffset), v2=str(b + voffset), v3=str(c + voffset))
                if i == 0 and var.get('support_paint') and var['support_paint'][fi]:
                    attrs['slic3rpe:custom_supports'] = var['support_paint'][fi]
                    has_support_paint = True
                ET.SubElement(tnode, 'triangle', **attrs)
            blocker = name == 'Tunnel support blocker'
            pocket = name == NFC_NAME
            kind = 'SupportBlocker' if blocker else 'NegativeVolume' if pocket or (i and settings['style'] == 'cut') else 'ModelPart'
            vc = ET.SubElement(oc, 'volume', firstid=str(tcount), lastid=str(tcount + len(faces) - 1))
            for key, value in [('name', safe_name(name)), ('volume_type', kind), ('matrix', '1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1')] + \
                    ([] if blocker else [('extruder', str(body if i == 0 or pocket else text))]):
                ET.SubElement(vc, 'metadata', type='volume', key=key, value=value)
            ET.SubElement(vc, 'mesh', edges_fixed='0', degenerate_facets='0', facets_removed='0', facets_reversed='0', backwards_edges='0')
            voffset += len(verts)
            tcount += len(faces)
    if len(palette) > MAX_EXTRUDERS:
        raise ValueError(f'PrusaSlicer supports up to {MAX_EXTRUDERS} filaments per project, and this batch uses {len(palette)}. '
                         'Use fewer colors, or turn off Actual Filament for the clip body or the text.')
    counts = {oid: 0 for oid in ids}
    for plate in plates:
        for item in plate['items']:
            oid = ids[item['variant']]
            counts[oid] += 1
            x = item['x'] + item['w'] / 2 + plate['origin'][0]
            y = item['y'] + item['h'] / 2 + plate['origin'][1]
            rot = '0 1 0 -1 0 0 0 0 1' if item['rotated'] else '1 0 0 0 1 0 0 0 1'
            ET.SubElement(build, 'item', objectid=str(oid), transform=f'{rot} {x:.6f} {y:.6f} 0', printable='1')
    for oc in cfg.findall('object'):
        oc.set('instances_count', str(counts[int(oc.get('id'))]))
    w, d, h = printer['bed']
    n = max(1, len(palette))
    support = settings.get('holder_sleeve') == 'yes' or has_support_paint
    ini = {
        'bed_shape': f'0x0,{w:g}x0,{w:g}x{d:g},0x{d:g}', 'max_print_height': f'{h:g}', 'nozzle_diameter': ','.join(['0.4'] * n),
        'extruder_colour': ';'.join(['""'] * n), 'filament_colour': ';'.join(c for _, c in palette) or '#FFFFFF',
        'temperature': ','.join(['210'] * n), 'first_layer_temperature': ','.join(['215'] * n), 'bed_temperature': ','.join(['60'] * n),
        'first_layer_bed_temperature': ','.join(['60'] * n), 'filament_diameter': ','.join(['1.75'] * n), 'extrusion_multiplier': ','.join(['1'] * n),
        'filament_type': ';'.join(['PLA'] * n), 'brim_width': '0', 'skirts': '0', 'wipe_tower': '1' if n > 1 else '0', 'complete_objects': '0',
        'support_material': '1' if support else '0', 'support_material_auto': '0' if support else '1',
        'support_material_threshold': '0', 'support_material_buildplate_only': '0', 'support_material_contact_distance': '0.2',
        'support_material_extruder': '0', 'support_material_interface_extruder': '0',
    }
    config = '\n'.join(f'; {k} = {v}' for k, v in ini.items()) + '\n'
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml', '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>')
        z.writestr('_rels/.rels', '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Target="/3D/3dmodel.model" Id="rel-1" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')
        z.writestr('3D/3dmodel.model', ET.tostring(model, encoding='utf-8', xml_declaration=True))
        z.writestr('Metadata/Slic3r_PE_model.config', ET.tostring(cfg, encoding='utf-8', xml_declaration=True))
        z.writestr('Metadata/Slic3r_PE.config', config)
        z.writestr('Metadata/Label_Batch.json', json.dumps(dict(printer=printer, settings=settings, plates=plates, filaments=palette,
                   notes='Open as a project and keep the project settings. Plate layout follows where each part sits: one grid cell per plate.')))
