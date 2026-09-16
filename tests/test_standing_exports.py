import sys,asyncio,subprocess,os,json,zipfile,collections,xml.etree.ElementTree as ET
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'author'))
import generator as g
from print_geometry import PROFILES
import tempfile
out=Path(tempfile.mkdtemp(prefix='clip-standing-test-'));g.CACHE=out/'cache';g.GENERATED=out/'generated';g.CACHE.mkdir(exist_ok=True);g.GENERATED.mkdir(exist_ok=True)
async def native(code,target):
 code=code.replace('"/author/','"'+str(root/'author')+'/');source=target.with_suffix('.scad');source.write_text(code)
 args=['--export-format','binstl'] if target.suffix=='.stl' else []
 p=subprocess.run(['arch','-x86_64','/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD','--backend=Manifold','--enable=textmetrics',*args,'-o',str(target),str(source)],capture_output=True,text=True,env=dict(os.environ,XDG_CACHE_HOME=str(out/'font-cache')))
 assert p.returncode==0 and 'ERROR:' not in p.stderr,p.stderr
 return p.stderr
g.run_scad=native
rows=[dict(product=next(p['id'] for p in g.CATALOG if p['manufacturer']==m and p['filament_type']==t and p['color_name']==c),quantity=2) for m,t,c in [('Bambu Lab','PETG-HF','Blue'),('Cookiecad','PLA','Dark Magic')]]
ns={'m':g.NS}
async def main():
 report=[]
 for sleeve in ['no','yes']:
  for style in ['part','cut','modifier']:
   review=await g.preflight(dict(rows=rows,settings=dict(holder_sleeve=sleeve,style=style)))
   result=await g.generate(review['key'],True)
   archive=g.GENERATED/Path(result['download']).name
   with zipfile.ZipFile(archive) as z:
    model=out/f'{sleeve}-{style}.3mf';model.write_bytes(z.read('Filament_Labels.3mf'))
   with zipfile.ZipFile(model) as z:
    assert z.testzip() is None
    xml=ET.fromstring(z.read('3D/3dmodel.model'));data=json.loads(z.read('Metadata/Label_Batch.json'))
    assert data['settings']['holder_sleeve']==sleeve
    assert len(xml.findall('.//m:build/m:item',ns))==4
    if sleeve=='yes':
     project=json.loads(z.read('Metadata/project_settings.config'))
     assert project['enable_support']=='1' and project['support_on_build_plate_only']=='0'
     assert project['support_top_z_distance']=='0.2' and project['support_bottom_z_distance']=='0.2'
     assert project['support_interface_top_layers']=='2' and project['support_interface_bottom_layers']=='2'
     assert sum(1 for t in xml.findall('.//m:triangle[@paint_supports]',ns))>0
     config=ET.fromstring(z.read('Metadata/model_settings.config'))
     assert len(config.findall('.//part[@subtype="support_blocker"]'))==2
    objects=xml.findall('m:resources/m:object',ns);bounds=[]
    for ob in objects:
     mesh=ob.find('m:mesh',ns)
     if mesh is None:continue
     vs=[tuple(float(v.get(k)) for k in ['x','y','z']) for v in mesh.find('m:vertices',ns)]
     assert min(v[2] for v in vs)>=-0.011 and max(v[2] for v in vs)<=(26 if sleeve=='yes' else 33)+1e-5
     if ob.get('name','').startswith('Clip body'):
      b=[(min(v[i] for v in vs),max(v[i] for v in vs)) for i in range(3)]
      profile='Bambu Original' if b[0][1]-b[0][0]>65 else 'Cookiecad'
      if sleeve=='yes':
       assert abs(b[1][1]-b[1][0]-33)<1e-4
       assert abs(b[2][1]-b[2][0]-PROFILES[profile]['depth'])<1e-4
      else:assert abs(b[2][1]-b[2][0]-33)<1e-5
      bounds.append(b)
      edges=collections.Counter()
      for f in mesh.find('m:triangles',ns):
       v=[int(f.get(k)) for k in ['v1','v2','v3']]
       for a,b in [(v[0],v[1]),(v[1],v[2]),(v[2],v[0])]:edges[tuple(sorted((a,b)))]+=1
      assert all(n==2 for n in edges.values()),'Nonmanifold body'
    assert len(bounds)==2
    for plate in data['plates']:
     for item in plate['items']:
      b=bounds[item['variant']];w=b[0][1]-b[0][0];h=b[1][1]-b[1][0]
      if item['rotated']:w,h=h,w
      assert w<=item['w']+1e-5 and h<=item['h']+1e-5
   report.append(dict(sleeve=sleeve,style=style,checks='pass',body_bounds=bounds))
   print(sleeve,style,'PASS',flush=True)
 (out/'results.json').write_text(json.dumps(report,indent=2))
asyncio.run(main())
