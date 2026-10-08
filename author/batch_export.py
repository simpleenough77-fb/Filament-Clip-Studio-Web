"""One Bambu Studio project containing every label and plate."""
import json,math,zipfile,io,re
import xml.etree.ElementTree as ET
from PIL import Image,ImageDraw
from nfc import NAME as NFC_NAME
from slicers import SLICERS,orca_settings
NS='http://schemas.microsoft.com/3dmanufacturing/core/2015/02'
def q(n):return '{'+NS+'}'+n
def safe_name(value):
    # Bambu Studio applies filename-style restrictions to object and plate names.
    return re.sub(r'\s+', ' ', re.sub(r'[<>:/\\|?*"\x00-\x1f]', '-', str(value))).strip(' .') or 'Label'
# Bambu Studio keeps a text part editable when the part carries a text_info record (text, font, size, thickness,
# embedded depth) next to its mesh. The mesh stays what the generator made until the user edits the text, when Bambu Studio
# rebuilds it from the record. Its text frame is a part-local frame turned 180 degrees about Y (the text reads from the
# bed side, so its +Z points into the clip), covering [-embedded, +thickness] around the local origin.
OPENSCAD_TO_EM=100/72      # OpenSCAD's text size is the letter height; Bambu Studio's font_size is the font's em size
TEXT_FLOOR=0.015           # Bambu Studio offsets text meshes by this much along its Z
def editable_text(verts,info,kind):
    """(part-local vertices, 3MF component transform, 4x4 matrix string, [(tag, attributes)]) for an editable text part.

    kind 'bambu': Bambu Studio's text_info. kind 'orca': Orca Slicer's slic3rpe:shape and slic3rpe:text records. Both keep the
    text part-local, turned 180 degrees about Y so it reads from the bed side; they differ in where the local origin sits
    along Z (Bambu Studio spans [-embedded, +thickness] around it, Orca [0, depth], both less the floor offset)."""
    xs=[v[0] for v in verts];ys=[v[1] for v in verts]
    cx=(min(xs)+max(xs))/2;cy=(min(ys)+max(ys))/2
    depth=info['depth'];em=info['size']*OPENSCAD_TO_EM
    tz=(depth/2-TEXT_FLOOR) if kind=='bambu' else (depth-TEXT_FLOOR)   # world z of the local origin; text spans world z [0, depth]
    local=[(cx-x,y-cy,tz-z) for x,y,z in verts]
    transform=f'-1 0 0 0 1 0 0 0 -1 {cx:.6f} {cy:.6f} {tz:.6f}'
    matrix=f'-1 0 0 {cx:.6f} 0 1 0 {cy:.6f} 0 0 -1 {tz:.6f} 0 0 0 1'
    if kind=='bambu':
        half=depth/2
        records=[('text_info',dict(text=info['text'],font_name=info['font'],font_version='',style_name='Recommend',boldness='0',skew='0',font_index='-1',font_size=f'{em:.4f}'.rstrip('0').rstrip('.'),thickness=f'{half:g}',embeded_depth=f'{half:g}',rotate_angle='0',text_gap='0',bold='0',italic='0',surface_type='1',hit_mesh='0',hit_position='0 0 0',hit_normal='0 0 0'))]
    else:
        # Orca's shape record: `scale` is the em size over the font's 2048 units per em (shapes are stored x1000), `depth` the
        # emboss depth, and `transform` the centre of the text mesh in the part's frame.
        records=[('slic3rpe:shape',dict(scale=repr(em/2048/1000),depth=f'{depth:g}',transform=f'1 0 0 0 1 0 0 0 1 0 0 {depth/2-TEXT_FLOOR:.9g}')),
                 ('slic3rpe:text',dict(text=info['text'],style_name='NORMAL',line_height=f'{em:.4f}'.rstrip('0').rstrip('.'),horizontal='center',vertical='middle',family='swiss',face_name=info['font']))]
    return local,transform,matrix,records
def meta(n,k,v):ET.SubElement(n,'metadata',key=k,value=safe_name(v) if k in ('name','plater_name') else str(v))
def write_batch(path,variants,plates,settings,printer,author,slicer='bambu_studio'):
    target=SLICERS[slicer]
    if target['family']=='prusa':
        from prusa_export import write_prusa
        return write_prusa(path,variants,plates,settings,printer,author)
    model=ET.Element(q('model'),unit='millimeter',attrib={'xml:lang':'en-US','xmlns:BambuStudio':'http://schemas.bambulab.com/package/2021'})
    for key,value in [('Title','Filament Labels'),('Application',target['app']),*target['extra'].items(),('BambuStudio:3mfVersion','1')]:ET.SubElement(model,q('metadata'),name=key).text=value
    res=ET.SubElement(model,q('resources'));build=ET.SubElement(model,q('build'));cfg=ET.Element('config')
    palette=[];slotmap={}
    # A printer without a multi-color system prints each plate in one filament: every part uses the one slot.
    single=settings.get('multicolor')=='no' and not printer.get('multi')
    def slot(role,color):
        if single:
            if not palette:palette.append((role,color))
            return 1
        key=(role,color)
        if key not in slotmap:slotmap[key]=len(palette)+1;palette.append(key)
        return slotmap[key]
    ids=[];oid=2
    for var in variants:
        r=var['check'];body=slot(r['filament_roles'][0],r['body_color']);text=body if settings['style']=='cut' else slot(r['filament_roles'][1],r['text_color'])
        aid=oid+len(var['parts']);ids.append(aid);oc=ET.SubElement(cfg,'object',id=str(aid));meta(oc,'name',' - '.join(r['lines']));meta(oc,'extruder',body)
        if target['family']=='orca' and (any(n=='Tunnel support blocker' for n,_ in var['parts']) or any(var.get('support_paint') or [])):
            # Keep manual supports on the object itself. A slicer that replaces the project's print profile with the user's own
            # (Snapmaker Orca does, for the U1) drops project-level support settings but keeps per-object ones.
            meta(oc,'enable_support','1');meta(oc,'support_type','normal(manual)')
        partids=[];transforms={}
        for i,(name,(verts,faces)) in enumerate(var['parts']):
            blocker=name=='Tunnel support blocker'
            textpart=None
            if target.get('text') and var.get('text') and 1<=i<=len(var['text']) and not blocker and name!=NFC_NAME:
                verts,transforms[oid],matrix,records=editable_text(verts,var['text'][i-1],target['text']);textpart=(matrix,records)
            partids.append(oid);obj=ET.SubElement(res,q('object'),id=str(oid),type='model',name=safe_name(name),pid='1',pindex=str((body if i==0 else text)-1))
            mesh=ET.SubElement(obj,q('mesh'));vnode=ET.SubElement(mesh,q('vertices'));tnode=ET.SubElement(mesh,q('triangles'))
            for x,y,z in verts:ET.SubElement(vnode,q('vertex'),x=str(x),y=str(y),z=str(z))
            for fi,(a,b,c) in enumerate(faces):
                attrs=dict(v1=str(a),v2=str(b),v3=str(c))
                if i==0 and var.get('support_paint') and var['support_paint'][fi]:attrs['paint_supports']=var['support_paint'][fi]
                ET.SubElement(tnode,q('triangle'),**attrs)
            pocket=name==NFC_NAME
            kind='negative_part' if pocket or (i and settings['style']=='cut') else 'normal_part'
            if blocker:kind='support_blocker'
            pc=ET.SubElement(oc,'part',id=str(oid),subtype=kind);meta(pc,'name',name+' | '+r['filament_roles'][0 if i==0 else 1]);meta(pc,'extruder',0 if blocker else body if i==0 or pocket else text);meta(pc,'matrix',textpart[0] if textpart else '1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1')
            if textpart:
                for tag,attrs in textpart[1]:ET.SubElement(pc,tag,**attrs)
            ET.SubElement(pc,'mesh_stat',face_count=str(len(faces)),edges_fixed='0',degenerate_facets='0',facets_removed='0',facets_reversed='0',backwards_edges='0');oid+=1
        assembly=ET.SubElement(res,q('object'),id=str(aid),type='model',name=safe_name(' - '.join(r['lines'])));comp=ET.SubElement(assembly,q('components'))
        for pid in partids:ET.SubElement(comp,q('component'),objectid=str(pid),**({'transform':transforms[pid]} if pid in transforms else {}))
        oid+=1
    mats=ET.Element(q('basematerials'),id='1');res.insert(0,mats)
    for role,color in palette:ET.SubElement(mats,q('base'),name=safe_name(role),displaycolor=color+'FF')
    counts={aid:0 for aid in ids};images={}
    for plate in plates:
        n=plate['number'];pc=ET.SubElement(cfg,'plate')
        for k,v in [('plater_id',n),('plater_name',f'{n}: '+plate['name']),('locked','false'),('filament_map_mode','Auto For Flush'),('thumbnail_file',f'Metadata/plate_{n}.png'),('thumbnail_no_light_file',f'Metadata/plate_no_light_{n}.png'),('top_file',f'Metadata/top_{n}.png')]:meta(pc,k,v)
        for item in plate['items']:
            aid=ids[item['variant']];inst=counts[aid];counts[aid]+=1
            x=item['x']+item['w']/2+plate['origin'][0];y=item['y']+item['h']/2+plate['origin'][1]
            rot='0 1 0 -1 0 0 0 0 1' if item['rotated'] else '1 0 0 0 1 0 0 0 1'
            ET.SubElement(build,q('item'),objectid=str(aid),transform=f'{rot} {x:.6f} {y:.6f} 0',printable='1')
            mi=ET.SubElement(pc,'model_instance');meta(mi,'object_id',aid);meta(mi,'instance_id',inst);meta(mi,'identify_id',sum(counts.values()))
        # Whole-plate thumbnail accurately reflects all variants and their placements.
        im=Image.new('RGB',(512,512),'#E8ECEF');draw=ImageDraw.Draw(im);scale=min(480/printer['bed'][0],480/printer['bed'][1]);ox=(512-printer['bed'][0]*scale)/2;oy=(512-printer['bed'][1]*scale)/2
        def xy(x,y):return (ox+x*scale,512-oy-y*scale)
        draw.rectangle([xy(0,printer['bed'][1]),xy(printer['bed'][0],0)],fill='#CBD2D7')
        if plate['tower']:
            a,b,c,d=plate['tower'];draw.rectangle([xy(a,d),xy(c,b)],outline='#78858A',width=1)
        for item in plate['items']:
            v=variants[item['variant']];cx=item['x']+item['w']/2;cy=item['y']+item['h']/2
            for index,(_,(verts,faces)) in enumerate(v['parts']):
                if _ in ('Tunnel support blocker',NFC_NAME) or (index and settings['style']=='cut'):continue
                color=v['check']['body_color'] if not index else v['check']['text_color']
                # Show the side-standing assembly footprint in plan view.
                for f in faces:
                    pts=[]
                    for k in f:
                        x,y,z=verts[k]
                        if item['rotated']:x,y=-y,x
                        pts.append(xy(cx+x,cy+y))
                    draw.polygon(pts,fill=color)
        b=io.BytesIO();im.save(b,format='PNG')
        for fn in [f'plate_{n}',f'plate_no_light_{n}',f'top_{n}']:images['Metadata/'+fn+'.png']=b.getvalue()
    if target['family']=='bambu' and printer.get('settings'):
        cfgsettings=json.loads((author/'Printer_Settings'/printer['settings']).read_text())
        # Export the stock Standard nozzle variant for each material slot.
        variant_fields = {'nozzle_temperature','nozzle_temperature_initial_layer','slow_down_min_speed'}
        for k,v in list(cfgsettings.items()):
            if isinstance(v,list) and (k.startswith('filament_') or k in variant_fields or k.endswith('_plate_temp') or k.endswith('_plate_temp_initial_layer')):
                if len(v)==3 and (k.startswith('filament_') or k in variant_fields):v=v[:1]
                cfgsettings[k]=v*len(palette)
        cfgsettings.update(name='Filament Labels',filament_colour=[c for _,c in palette],filament_multi_colour=[c for _,c in palette],filament_map=['1']*len(palette),filament_nozzle_map=['0']*len(palette),filament_colour_type=['0']*len(palette),filament_self_index=[str(i+1) for i in range(len(palette))],filament_extruder_variant=['Direct Drive Standard']*len(palette),enable_prime_tower='1' if any(p['tower'] for p in plates) else '0',prime_tower_width='60',prime_tower_brim_width='3',prime_tower_extra_rib_length='0',prime_tower_enable_framework='0',brim_type='no_brim',skirt_loops='0')
        # A sleeve project must carry explicit manual-support settings. Detect the
        # blocker part as well as the UI setting so an exported project cannot fall
        # back to the printer preset's disabled/auto-support defaults.
        has_sleeve = settings.get('holder_sleeve') == 'yes' or any(
            any(name == 'Tunnel support blocker' for name, _ in var.get('parts', []))
            for var in variants
        )
        if has_sleeve:
            cfgsettings.update(json.loads((author/'Tested_Support_Settings.json').read_text()))
            cfgsettings.update(enable_support='1', support_type='normal(manual)', support_filament='0', support_interface_filament='0', enable_arc_fitting='0', version='02.08.02.61')
            cfgsettings['different_settings_to_system']=['enable_arc_fitting;enable_support;support_type','','','','','']
            cfgsettings['from']='project'
        cfgsettings['wipe_tower_x']=[str(p['tower'][0]+8 if p['tower'] else 0) for p in plates];cfgsettings['wipe_tower_y']=[str(p['tower'][1]+8 if p['tower'] else 0) for p in plates]
        # Studio stores one complete filament-to-filament matrix per physical nozzle.
        nozzle_count=len(cfgsettings['nozzle_diameter'])
        cfgsettings['flush_volumes_matrix']=['0' if i==j else '140' for nozzle in range(nozzle_count) for i in range(len(palette)) for j in range(len(palette))]
        cfgsettings['flush_multiplier']=['1']*nozzle_count
        cfgsettings['flush_multiplier_fast']=['1.2']*nozzle_count
        cfgsettings['flush_volumes_vector']=['140']*(2*len(palette))
    else:
        has_sleeve=settings.get('holder_sleeve')=='yes' or any(any(name=='Tunnel support blocker' for name,_ in var.get('parts',[])) for var in variants)
        support=json.loads((author/'Tested_Support_Settings.json').read_text()) if has_sleeve else None
        cfgsettings=orca_settings(palette,plates,printer,support)
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml','<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/><Default Extension="config" ContentType="application/octet-stream"/><Default Extension="png" ContentType="image/png"/><Default Extension="json" ContentType="application/json"/></Types>')
        z.writestr('_rels/.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')
        z.writestr('3D/3dmodel.model',ET.tostring(model,encoding='utf-8',xml_declaration=True));z.writestr('Metadata/model_settings.config',ET.tostring(cfg,encoding='utf-8',xml_declaration=True));z.writestr('Metadata/project_settings.config',json.dumps(cfgsettings));z.writestr('Metadata/slice_info.config','<?xml version="1.0" encoding="UTF-8"?><config><header><header_item key="X-BBL-Client-Type" value="slicer"/><header_item key="X-BBL-Client-Version" value="02.08.02.61"/></header></config>')
        z.writestr('Metadata/Label_Batch.json',json.dumps(dict(printer=printer,settings=settings,plates=plates,filaments=palette,notes='Assign actual compatible filament presets in Bambu Studio. Placement reserves bed/nozzle keep-outs and prime-tower space; inspect slicing before printing.')))
        for name,data in images.items():z.writestr(name,data)
