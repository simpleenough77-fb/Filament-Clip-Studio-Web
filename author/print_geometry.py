"""Author-approved body selection and a rigid side-standing print transform."""
import json
PROFILES={
    'Bambu Original':dict(width=68.0,depth=18.56409,stem='bambu'),
    'Cookiecad':dict(width=62.5,depth=24.11825,stem='cookiecad'),
}
def body_code(profile,sleeve=False):
    p=PROFILES[profile]
    if sleeve:
        # Supplied STL is standing at positive XYZ. Normalize into the existing
        # label coordinate system; no mesh edits, scaling or inferred collar.
        matrix=[[1,0,0,-p['width']/2],[0,0,-1,16.5],[0,1,0,0],[0,0,0,1]]
        return 'multmatrix('+json.dumps(matrix)+')import("/author/'+p['stem']+'_sleeve.stl");'
    return 'import("/author/'+p['stem']+'.stl");'
def footprint(profile):
    p=PROFILES[profile]
    # 0.01 mm on either side also contains engraving negative-part extensions.
    return p['width'],p['depth']+0.02

def standing_parts(parts,profile):
    depth=PROFILES[profile]['depth']
    return [(name,([(x,z-depth/2,16.5-y) for x,y,z in vertices],faces))
            for name,(vertices,faces) in parts]
