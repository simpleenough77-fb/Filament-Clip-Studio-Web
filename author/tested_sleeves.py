"""Owner-tested sleeve bodies, support painting and tunnel exclusion volumes."""
import json
from pathlib import Path
from functools import lru_cache
@lru_cache(None)
def reference():
    return json.loads(Path(__file__).with_name('Tested_Sleeves.json').read_text())
def body_mesh(profile):
    """Return the exact body mesh captured from the owner-tested sleeve project."""
    src=reference()[profile]['body']
    return src['vertices'],src['faces']
def key(vertices,face):
    return tuple(sorted(tuple(round(c,4) for c in vertices[i]) for i in face))
def sleeve_parts(profile,body_mesh):
    src=reference()[profile];body=src['body']
    painted={key(body['vertices'],f):p for f,p in zip(body['faces'],body['paint']) if p}
    vertices,faces=body_mesh
    flags=[painted.get(key(vertices,f),'') for f in faces]
    flags=transferred_paint(profile,vertices,faces,flags)
    return flags,('Tunnel support blocker',(src['blocker']['vertices'],src['blocker']['faces']))

@lru_cache(None)
def painted_grid(profile):
    import math
    src=reference()[profile]['body'];grid={}
    for f,p in zip(src['faces'],src['paint']):
        if not p:continue
        tri=[src['vertices'][i] for i in f]
        lo=[math.floor(min(v[i] for v in tri)/4) for i in range(3)]
        hi=[math.floor(max(v[i] for v in tri)/4) for i in range(3)]
        for x in range(lo[0],hi[0]+1):
            for y in range(lo[1],hi[1]+1):
                for z in range(lo[2],hi[2]+1):grid.setdefault((x,y,z),[]).append((tri,p))
    return grid

def transferred_paint(profile,vertices,faces,flags):
    """Recover paint on coplanar faces retriangulated by the inlay Boolean."""
    import math
    grid=painted_grid(profile)
    def sub(a,b):return [x-y for x,y in zip(a,b)]
    def dot(a,b):return sum(x*y for x,y in zip(a,b))
    for i,f in enumerate(faces):
        if flags[i]:continue
        pt=[sum(vertices[j][k] for j in f)/3 for k in range(3)]
        for tri,p in grid.get(tuple(math.floor(x/4) for x in pt),[]):
            a,b,c=tri;u=sub(b,a);v=sub(c,a);w=sub(pt,a)
            uu=dot(u,u);uv=dot(u,v);vv=dot(v,v);wu=dot(w,u);wv=dot(w,v);den=uu*vv-uv*uv
            if abs(den)<1e-16:continue
            s=(vv*wu-uv*wv)/den;t=(uu*wv-uv*wu)/den
            if s< -1e-4 or t< -1e-4 or s+t>1.0001:continue
            if sum((w[k]-s*u[k]-t*v[k])**2 for k in range(3))<1e-10:
                flags[i]=p;break
    return flags
