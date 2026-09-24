"""Private local batch companion. Requires OpenSCAD and Pillow (PNG previews)."""
from pathlib import Path
import csv,io,json,hashlib,secrets,subprocess,os,sys,re,struct,zipfile,xml.etree.ElementTree as ET

from urllib.parse import urlparse

ROOT=Path(__file__).resolve().parent.parent
AUTHOR=ROOT/'author'; GENERATED=ROOT/'Generated'; CACHE=ROOT/'.cache'
CATALOG=json.loads((AUTHOR/'Catalog.json').read_text())['products']
PRODUCTS={p['id']:p for p in CATALOG}
PRINTERS=json.loads((AUTHOR/'Printers.json').read_text())
from placement import plan
from print_geometry import body_code,standing_parts
import batch_library
LIBRARY=ROOT/"Batch_Library.json"
FONTS=['Liberation Sans:style=Bold','DejaVu Sans:style=Bold','Liberation Serif:style=Bold']
TOKEN=secrets.token_urlsafe(24); PREFLIGHTS={}
NS='http://schemas.microsoft.com/3dmanufacturing/core/2015/02'
ET.register_namespace('',NS)
def q(tag):return '{'+NS+'}'+tag

async def run_scad(code,target):
    from js import compileScad
    result=json.loads(await compileScad(code,target.suffix))
    import base64
    target.parent.mkdir(exist_ok=True,parents=True)
    target.write_bytes(base64.b64decode(result['bytes']))
    return result['log']

def includes():
    return 'use <'+str(AUTHOR/'Accepted_Geometry.scad')+'>\nuse <'+str(AUTHOR/'Labels.scad')+'>\n'
def valid_color(s):
    if not isinstance(s,str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',s):raise ValueError('Choose a valid color.')
    return s.upper()
def validate(data, allow_empty=False):
    rows=data.get('rows',[]); settings=data.get('settings',{})
    if not (0 if allow_empty else 1)<=len(rows)<=100:raise ValueError('Add between 1 and 100 label variants.')
    s={k:settings.get(k,v) for k,v in dict(font=FONTS[0],type_size=6,vendor_size=0,color_size=0,style='part',holder_sleeve='no',body_mode='fixed',body_color='#000000',text_mode='contrast',printer='H2D',text_color='#00AE42',dark_color='#151515',light_color='#FFFFFF').items()}
    if s['holder_sleeve'] not in ('no','yes'):raise ValueError('Choose whether to include a holder sleeve.')
    if s['printer'] not in PRINTERS:raise ValueError('Choose an available printer.')
    if s['font'] not in FONTS:raise ValueError('Choose an available font.')
    for k in ('type_size','vendor_size','color_size'):
        s[k]=float(s[k]);
        if k!='type_size' and s[k]==0:s[k]=s['type_size']*.8
        elif not 2<=s[k]<=8:raise ValueError('Font sizes must be 2–8 mm; use 0 for automatic manufacturer/color sizing.')
    if s['style'] not in ('part','cut','modifier'):raise ValueError('Unknown label style.')
    if s['body_mode'] not in ('fixed','filament') or s['text_mode'] not in ('fixed','filament','contrast'):raise ValueError('Unknown color mode.')
    for k in ('body_color','text_color','dark_color','light_color'):s[k]=valid_color(s[k])
    clean=[]
    for r in rows:
        if r.get('product') not in PRODUCTS:raise ValueError('A product is not in the approved catalog.')
        p=PRODUCTS[r['product']]
        profile=p['spool_profile'] # Author-maintained manufacturer/spool mapping
        if profile not in ('Bambu Original','Cookiecad','Amolen 1kg'):raise ValueError('Choose an accepted spool profile.')
        n=r.get('quantity',1)
        if isinstance(n,bool) or str(n)!=str(int(n)) or not 1<=int(n)<=100:raise ValueError('Quantities must be whole numbers from 1 to 100.')
        swatch=r.get('swatch') or p.get('swatch')
        if swatch:swatch=valid_color(swatch)
        clean.append(dict(product=p['id'],quantity=int(n),spool_profile=profile,swatch=swatch))
    if sum(r['quantity'] for r in clean)>100:raise ValueError('Limit each batch to 100 clips.')
    return dict(rows=clean,settings=s)

def luminance(hex):
    vals=[int(hex[i:i+2],16)/255 for i in (1,3,5)]
    vals=[v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in vals]
    return sum(a*b for a,b in zip(vals,[.2126,.7152,.0722]))
def contrast(a,b):
    x,y=sorted([luminance(a),luminance(b)]);return (y+.05)/(x+.05)
def palette(r):
    p=PRODUCTS[r['product']]
    return [r['swatch']] if r.get('swatch') and r['swatch']!=p.get('swatch') else p.get('preview_palette') or [r.get('swatch') or '#707B83']

def colors(r,s):
    body=(r['swatch'] or '#707B83') if s['body_mode']=='filament' else '#000000'
    if s['text_mode']=='filament':text=r['swatch'] or '#707B83'
    elif s['text_mode']=='contrast':
        backgrounds=palette(r) if s['body_mode']=='filament' else [body]
        text='#00AE42' if s['body_mode']=='fixed' else max(['#151515','#FFFFFF'],key=lambda c:min(contrast(c,b) for b in backgrounds))
    else:text='#00AE42'
    return body,text

def filament_roles(r,s):
    p=PRODUCTS[r['product']];product=' / '.join([p['manufacturer'],p['filament_type'],p['color_name']])
    text=product if s['text_mode']=='filament' else ('Bambu Green' if s['body_mode']=='fixed' else 'Light' if colors(r,s)[1]=='#FFFFFF' else 'Dark')+' contrasting filament - choose matching filament in slicer' if s['text_mode']=='contrast' else 'Shared text filament - choose in slicer'
    return [product if s['body_mode']=='filament' else 'Shared black body filament - choose in slicer',text]

async def preflight(data):
    data=validate(data);s=data['settings'];sizes=[s['vendor_size'],s['type_size'],s['color_size']]
    checks=[];code=includes()
    for i,r in enumerate(data['rows']):
        p=PRODUCTS[r['product']];lines=[p['manufacturer'],p['filament_type'],p['color_name']];width={'Bambu Original':68,'Cookiecad':62.5,'Amolen 1kg':61}[r['spool_profile']]-4
        for j,t in enumerate(lines):
            code+=f'let(t={json.dumps(t)},sz={sizes[j]},font={json.dumps(s["font"])},f=label_fit(t,sz,font,{width}),m=textmetrics(f,size=sz,font=font)) echo([{i},{j},t,f,m.size.x,m.size.y]);\n'
        checks.append(dict(**r,lines=lines,display=[],width=width,body_color=colors(r,s)[0],text_color=colors(r,s)[1],filament_roles=filament_roles(r,s),swatch_palette=palette(r),swatch_effects=p.get('swatch_effects',[]),swatch_description=p.get('swatch_description',''),body_actual=s['body_mode']=='filament',text_actual=s['text_mode']=='filament'))
    code+='cube(.01);\n';target=CACHE/'metrics.csg'
    log=await run_scad(code,target);warnings=[]
    echoes=[]
    for line in log.splitlines():
        if line.startswith('ECHO: ['):echoes.append(json.loads(line[6:]))
    if len(echoes)!=len(checks)*3:raise ValueError('Could not measure all labels; verify OpenSCAD textmetrics support.')
    for i,j,original,short,width,height in echoes:
        if height>8 or width>checks[i]['width']+.001:raise ValueError('Font too large for '+original+'. Reduce its size.')
        checks[i]['display'].append(short)
        if original!=short:warnings.append(dict(row=i+1,line=['Manufacturer','Type','Color/name'][j],original=original,truncated=short))
    for r in checks:
        svgcode=includes()+f'projection()label_all({json.dumps(r["lines"],ensure_ascii=False)},{json.dumps(sizes)},{json.dumps(s["font"])},{r["width"]});'
        svgfile=CACHE/'preview.svg';await run_scad(svgcode,svgfile)
        svg=ET.fromstring(svgfile.read_text())
        r['paths']=[node.attrib['d'] for node in svg.iter() if node.tag.endswith('path')]
    plates=plan(checks,s,PRINTERS[s['printer']])
    key=hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()
    PREFLIGHTS[key]=(data,checks,warnings)
    return dict(key=key,rows=checks,warnings=warnings,total=sum(r['quantity'] for r in checks),sizes=sizes,font=s['font'],style=s['style'],plates=plates,printer=PRINTERS[s['printer']])

def load_stl(path):
    raw=path.read_bytes()
    if len(raw)>=84 and 84+50*struct.unpack_from('<I',raw,80)[0]==len(raw):
        triangles=[struct.unpack_from('<12f',raw,84+50*i)[3:] for i in range(struct.unpack_from('<I',raw,80)[0])]
    else:
        points=[tuple(map(float,v)) for v in re.findall(rb'vertex\s+([-+\deE.]+)\s+([-+\deE.]+)\s+([-+\deE.]+)',raw)]
        triangles=[sum(points[i:i+3],()) for i in range(0,len(points),3)]
    verts=[];faces=[];lookup={}
    for tri in triangles:
        face=[]
        for i in (0,3,6):
            pt=tuple(round(v,6) for v in tri[i:i+3])
            if pt not in lookup:lookup[pt]=len(verts);verts.append(pt)
            face.append(lookup[pt])
        # STL float conversion can collapse a microscopic edge to one vertex.
        # Such triangles have no surface area and must not enter the 3MF mesh.
        if len(set(face))==3:faces.append(face)
    if not faces:raise ValueError('Empty mesh '+str(path))
    return verts,faces

def mesh_thumbnail(parts,body_color,text_color,style,quantity,front=True):
    from PIL import Image,ImageDraw
    im=Image.new('RGB',(512,512),'#EDF2F4');draw=ImageDraw.Draw(im)
    count=min(quantity,9);columns=min(3,count);rows=(count+2)//3
    scale=min(480/(columns*74),480/(rows*40))
    tris=[]
    for index,(_,path) in enumerate(parts):
        if index>0 and style=='cut':continue
        vs,fs=load_stl(path)
        for f in fs:
            v=[vs[k] for k in f]
            # Painter order is exact for these planar front faces. Front label view
            # includes the unmodified rear silhouette behind the label face.
            depth=sum(t[2] for t in v)/3
            tris.append(((-depth if front else depth),v,body_color if index==0 else text_color))
    tris.sort(key=lambda t:t[0])
    for k in range(count):
        cx=256+(k%3-(columns-1)/2)*74*scale
        cy=256+(k//3-(rows-1)/2)*40*scale
        for _,v,col in tris:
            pts=[(cx+x*scale,cy+(y if front else -y)*scale) for x,y,z in v]
            draw.polygon(pts,fill=col)
    b=io.BytesIO();im.save(b,format='PNG');return b.getvalue()

def make_3mf(path,parts,name,body_color,text_color,style,quantity=1,roles=None,same_filament=False):
    model=ET.Element(q('model'),unit='millimeter',attrib={'xml:lang':'en-US','xmlns:BambuStudio':'http://schemas.bambulab.com/package/2021'})
    ET.SubElement(model,q('metadata'),name='Title').text=name
    ET.SubElement(model,q('metadata'),name='Application').text='BambuStudio-02.08.02.61'
    ET.SubElement(model,q('metadata'),name='BambuStudio:3mfVersion').text='1'
    ET.SubElement(model,q('metadata'),name='Designer').text='Independent Clip Label Generator'
    if roles:ET.SubElement(model,q('metadata'),name='Description').text='Filament assignments: body: '+roles[0]+'; text: '+roles[1]+'. Select actual filament presets in the slicer.'
    res=ET.SubElement(model,q('resources')); mats=ET.SubElement(res,q('basematerials'),id='1')
    for label,c in [('Clip body',body_color),('Label text',text_color)]:ET.SubElement(mats,q('base'),name=label,displaycolor=c+'FF')
    config=ET.Element('config');obj=ET.SubElement(config,'object',id='10')
    ET.SubElement(obj,'metadata',key='name',value=name);ET.SubElement(obj,'metadata',key='extruder',value='1')
    for i,(label,stl) in enumerate(parts):
        oid=str(i+2);verts,faces=load_stl(stl)
        meshobj=ET.SubElement(res,q('object'),id=oid,type='model',name=label,pid='1',pindex=str(0 if i==0 else 1))
        mesh=ET.SubElement(meshobj,q('mesh'));vnode=ET.SubElement(mesh,q('vertices'));tnode=ET.SubElement(mesh,q('triangles'))
        for x,y,z in verts:ET.SubElement(vnode,q('vertex'),x=str(x),y=str(y),z=str(z))
        for a,b,c in faces:ET.SubElement(tnode,q('triangle'),v1=str(a),v2=str(b),v3=str(c))
        subtype='normal_part' if i==0 or style=='part' else 'negative_part' if style=='cut' else 'modifier_part'
        part=ET.SubElement(obj,'part',id=oid,subtype=subtype)
        ET.SubElement(part,'metadata',key='name',value=label+(' | '+roles[0 if i==0 else 1] if roles else ''))
        ET.SubElement(part,'metadata',key='extruder',value=str(1 if i==0 or style=='cut' or same_filament else 2))
        ET.SubElement(part,'metadata',key='matrix',value='1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1')
        ET.SubElement(part,'mesh_stat',face_count=str(len(faces)),edges_fixed='0',degenerate_facets='0',facets_removed='0',facets_reversed='0',backwards_edges='0')
    assembly=ET.SubElement(res,q('object'),id='10',type='model',name=name);components=ET.SubElement(assembly,q('components'))
    for i in range(len(parts)):ET.SubElement(components,q('component'),objectid=str(i+2))
    build=ET.SubElement(model,q('build'))
    for instance in range(quantity):
        x=42+(instance%3)*74;y=30+(instance//3)*40
        ET.SubElement(build,q('item'),objectid='10',transform=f'1 0 0 0 1 0 0 0 1 {x} {y} 0',printable='1')
    plate=ET.SubElement(config,'plate')
    for k,v in [('plater_id','1'),('plater_name',name),('locked','false'),('filament_map_mode','Auto For Flush'),('thumbnail_file','Metadata/plate_1.png'),('thumbnail_no_light_file','Metadata/plate_no_light_1.png'),('top_file','Metadata/top_1.png')]:ET.SubElement(plate,'metadata',key=k,value=v)
    for instance in range(quantity):
        node=ET.SubElement(plate,'model_instance')
        for k,v in [('object_id','10'),('instance_id',str(instance)),('identify_id',str(instance+1))]:ET.SubElement(node,'metadata',key=k,value=v)
    settings=json.loads((AUTHOR/'Print_Settings_H2D.json').read_text())
    settings['filament_colour']=[body_color,text_color]
    settings['name']=name
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
        front=mesh_thumbnail(parts,body_color,text_color,style,quantity,True)
        z.writestr('Metadata/plate_1.png',front)
        z.writestr('Metadata/plate_no_light_1.png',front)
        z.writestr('Metadata/top_1.png',mesh_thumbnail(parts,body_color,text_color,style,quantity,False))
        z.writestr('[Content_Types].xml','<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/><Default Extension="config" ContentType="application/octet-stream"/><Default Extension="png" ContentType="image/png"/></Types>')
        z.writestr('_rels/.rels','<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')
        z.writestr('3D/3dmodel.model',ET.tostring(model,encoding='utf-8',xml_declaration=True))
        z.writestr('Metadata/model_settings.config',ET.tostring(config,encoding='utf-8',xml_declaration=True))
        z.writestr('Metadata/project_settings.config',json.dumps(settings,indent=2))

async def generate(key,ack=False):
    GENERATED.mkdir(exist_ok=True,parents=True)
    if key not in PREFLIGHTS:raise ValueError('Review this batch before generating.')
    data,checks,warnings=PREFLIGHTS[key]
    if warnings and ack is not True:raise ValueError('Accept the displayed truncations before generation.')
    from batch_export import write_batch
    s=data['settings'];sizes=[s['vendor_size'],s['type_size'],s['color_size']]
    out=GENERATED/(key[:12]+'-'+secrets.token_hex(3));out.mkdir(parents=True)
    meshdir=CACHE/out.name;meshdir.mkdir()
    variants=[]
    for index,r in enumerate(checks):
        params=f'lines={json.dumps(r["lines"],ensure_ascii=False)}; sizes={json.dumps(sizes)}; font={json.dumps(s["font"])}; width={r["width"]};\n'
        base=includes()+params;geometry=body_code(r['spool_profile'],s['holder_sleeve']=='yes')
        # Use the owner-tested sleeve mesh directly. Running it through the
        # label Boolean can recreate the small tunnel/plate notch.
        if s['holder_sleeve']=='yes':
            from tested_sleeves import body_mesh
            bodymesh=body_mesh(r['spool_profile'])
        else:
            bodycode=base+(('difference(){'+geometry+'translate([0,0,-.01])label_all(lines,sizes,font,width,.61);}') if s['style']=='part' else geometry)
            bodyfile=meshdir/f'{index}_body.stl';await run_scad(bodycode,bodyfile)
            bodymesh=load_stl(bodyfile)
        parts=[('Clip body'+(' with holder sleeve' if s['holder_sleeve']=='yes' else '')+' - '+r['spool_profile'],bodymesh)]
        for i,label in enumerate(['Manufacturer','Filament type','Color name']):
            path=meshdir/f'{index}_{i}.stl'
            code=base+(f'translate([0,0,-.01])label_line(lines,sizes,font,width,{i},.61);' if s['style']=='cut' else f'label_line(lines,sizes,font,width,{i},.6);')
            await run_scad(code,path);parts.append((label+' - '+r['display'][i],load_stl(path)))
        if s['holder_sleeve']=='yes':
            from tested_sleeves import sleeve_parts
            flags,blocker=sleeve_parts(r['spool_profile'],parts[0][1])
            # The supplied Amolen project is already standing on its side.
            # Rotate only its generated text modifiers into that same frame;
            # the owner-tested body and blocker are already in standing axes.
            if r['spool_profile']=='Amolen 1kg':
                parts=[parts[0]]+standing_parts(parts[1:],r['spool_profile'])
            parts.append(blocker)
            variants.append(dict(check=r,parts=parts,support_paint=flags))
        else:
            variants.append(dict(check=r,parts=standing_parts(parts,r['spool_profile'])))
    plates=plan(checks,s,PRINTERS[s['printer']])
    write_batch(out/'Filament_Labels.3mf',variants,plates,s,PRINTERS[s['printer']],AUTHOR)
    with (out/'Labels.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f);w.writerow(['manufacturer','filament_type','color_name','quantity'])
        for r in checks:
            p=PRODUCTS[r['product']];w.writerow([p['manufacturer'],p['filament_type'],p['color_name'],r['quantity']])
    archive=out.with_suffix('.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for file in out.iterdir():z.write(file,file.name)
    return dict(download='/generated/'+archive.name,plates=len(plates),total=sum(r['quantity'] for r in checks))

def import_csv(text, capacity=100):
    reader=csv.reader(io.StringIO(text.lstrip('\ufeff')))
    header=next(reader,None)
    if not header:raise ValueError('The CSV is empty.')
    header=[f.strip().lower() for f in header]
    required=['manufacturer','filament_type','color_name','quantity']
    if not set(required)<=set(header) or len(set(header))!=len(header):raise ValueError('CSV headers must include each field once: '+', '.join(required))
    rows=[];skipped=[];total=0;previous=reader.line_num
    for values in reader:
        line=previous+1;previous=reader.line_num
        if not any(v.strip() for v in values):continue
        record=dict(zip(header,values));record['_extra']=values[len(header):]
        reason=None
        triple=[(record.get(k) or '').strip().casefold() for k in required[:3]]
        match=[p for p in CATALOG if triple==[p[k].casefold() for k in required[:3]] or triple in [[v.casefold() for v in a] for a in p.get('label_aliases',[])]]
        if record.get('_extra'):reason='Extra CSV fields; quote names containing commas.'
        elif len(match)!=1:reason='Manufacturer, type and color combination not found.'
        try:
            qty=(record.get('quantity') or '').strip()
            if not re.fullmatch(r'[0-9]+',qty) or not 1<=int(qty)<=100:raise ValueError()
            qty=int(qty)
        except ValueError:
            qty=0;reason=reason or 'Quantity must be a whole number from 1 to 100.'
        if not reason and (total+qty>capacity or len(rows)>=100):reason='This row would exceed the 100-clip batch limit; reduce quantities or choose Replace current batch.'
        if reason:skipped.append(dict(row=line,**{k:record.get(k) or '' for k in required},reason=reason));continue
        rows.append(dict(product=match[0]['id'],quantity=qty,swatch=match[0]['swatch']));total+=qty
    return dict(rows=rows,skipped=skipped,imported=len(rows),total=total)
