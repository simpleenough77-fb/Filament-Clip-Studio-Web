"""Author-approved body selection and a rigid side-standing print transform."""
import json
PROFILES={
    'Bambu Original':dict(width=68.0,depth=18.56409,sleeve_depth=18.5640869140625,stem='bambu'),
    'Cookiecad':dict(width=62.5,depth=24.11825,sleeve_depth=24.11822509765625,stem='cookiecad'),
    'Amolen 1kg':dict(width=61.0,depth=17.6,sleeve_depth=18.0,stem='amolen'),
}
def body_code(profile,sleeve=False):
    p=PROFILES[profile]
    if sleeve:
        return 'import("/author/'+p['stem']+'_tested_sleeve.stl");'
    return 'import("/author/'+p['stem']+'.stl");'
def footprint(profile,sleeve=False):
    p=PROFILES[profile]
    # 0.01 mm on either side also contains engraving negative-part extensions.
    return (p['width'],35.5) if sleeve else (p['width'],p['depth']+0.02)

def standing_parts(parts,profile):
    depth=PROFILES[profile]['depth']
    return [(name,([(x,z-depth/2,16.5-y) for x,y,z in vertices],faces))
            for name,(vertices,faces) in parts]
