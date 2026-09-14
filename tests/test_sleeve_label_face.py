"""Check the real exterior label face, not merely overall mesh bounds."""
import sys, math, tempfile, subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'author'))
from generator import load_stl
from print_geometry import PROFILES, body_code, standing_parts
out=Path(tempfile.mkdtemp(prefix='clip-face-test-'))
for profile,p in PROFILES.items():
 source=out/(p['stem']+'.scad'); target=source.with_suffix('.stl')
 source.write_text(body_code(profile,True).replace('"/author/','"'+str(root/'author')+'/'))
 subprocess.run(['arch','-x86_64','/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD','--backend=Manifold','--export-format','binstl','-o',str(target),str(source)],check=True,capture_output=True)
 vertices,faces=load_stl(target)
 area=0
 for f in faces:
  a,b,c=[vertices[i] for i in f]
  if max(abs(v[2]) for v in (a,b,c))<0.0001:
   cross=(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
   assert cross<0, 'Label exterior must face outward toward negative canonical Z'
   area+=abs(cross)/2
 assert area>1900, (profile,area,'Text plane is not the broad label face')
 # Positive text extrusion goes inward from that face after the same rigid rotation.
 transformed=standing_parts([('text',([(0,0,0),(0,0,.6)],[]))],profile)[0][1][0]
 assert abs(transformed[0][1]+p['depth']/2)<1e-7
 assert abs(transformed[1][1]-transformed[0][1]-.6)<1e-7
 print(profile, 'PASS; exterior label area',round(area,3),'mm2')
