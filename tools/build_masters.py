from pathlib import Path
import subprocess,os
root=Path(__file__).resolve().parent.parent/"author"
for profile,name in [('Bambu Original','bambu'),('Cookiecad','cookiecad')]:
 p=root/(name+'.scad');p.write_text('use <Accepted_Geometry.scad>\naccepted_body("'+profile+'");\n')
 env=dict(os.environ,XDG_CACHE_HOME='/tmp/clip-font-cache')
 subprocess.run(['arch','-x86_64','/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD','--backend=Manifold','--export-format','binstl','-o',str(root/(name+'.stl')),str(p)],check=True,env=env)
