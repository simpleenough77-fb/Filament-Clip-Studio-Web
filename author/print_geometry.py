"""Owner-supplied clip bodies, one STL pair per vendor, and their footprints.

Every body is modelled face down: the front (label) face lies on z = 0 and the legs rise from the back, so clips print flat
on the bed with or without a holder sleeve. Bodies are centred on X/Y. `size` is the body's bounding box (x, y, z) in mm;
`width` is the plate width the label text is fitted to (text gets width - 4 mm). `leg_inner` is the |x| of each leg's inner
face and `sleeve_top` the height of the top of the sleeve plate (both used by the NFC pocket), measured from the shipped
meshes. Each vendor has its own file pair (<stem>.stl, <stem>_sleeve.stl) so one vendor can change without touching another.
`plate` is the thickness of the faceplate (the back of the plate, where an NFC pocket goes) and `bore_z` the height of the
filament bore's axis above the front face (both used by the sleeve support rules and the NFC pocket).
"""
def _p(stem,width,size,leg_inner,sleeve_top,plate=3.6,bore_z=5.5):
    return dict(stem=stem,width=width,size=size,depth=size[2],leg_inner=leg_inner,sleeve_top=sleeve_top,plate=plate,bore_z=bore_z)
_BAMBU=dict(width=68.0,size=(68.0,33.0,18.564),leg_inner=28.25,sleeve_top=13.25)
_SUNLU=dict(width=68.0,size=(68.0,33.0,17.032),leg_inner=28.25,sleeve_top=13.1)
_CARDBOARD=dict(width=67.0,size=(67.004,46.049,16.587),leg_inner=28.02,sleeve_top=13.1)
PROFILES={
    'Bambu Original':_p('bambu',**_BAMBU),
    'Cookiecad':_p('cookiecad',62.5,(62.5,33.0,24.118),24.0,13.25),
    'Amolen 1kg':_p('amolen',61.0,(61.102,33.0,18.0),26.0,13.1),
    'Sunlu 1kg':_p('sunlu',**_SUNLU),
    'Jayo 1.1kg':_p('jayo',**_SUNLU),
    'Polymaker 1kg':_p('polymaker',**_CARDBOARD),
    'Panchroma 1kg':_p('panchroma',**_CARDBOARD),
    'Inland 1kg':_p('inland',**_CARDBOARD),
    'Protopasta':_p('protopasta',70.0,(70.0,33.0,15.5),29.5,12.5,plate=3.0,bore_z=5.0),
    'Geeetech 1kg':_p('geeetech',54.0,(54.0,55.935,21.279),23.0,12.5,plate=3.0,bore_z=4.5),
    'Creality 1kg':_p('creality',72.0,(72.0,33.006,15.5),27.94,12.5,plate=3.0,bore_z=5.0),
}
def body_code(profile,sleeve=False):
    p=PROFILES[profile]
    return 'import("/author/'+p['stem']+('_sleeve' if sleeve else '')+'.stl");'
def footprint(profile,sleeve=False):
    """(x, y) the clip occupies on the plate. The sleeve version leaves room for the tunnel support blocker."""
    w,h,_=PROFILES[profile]['size']
    # 0.01 mm on either side also contains engraving negative-part extensions.
    return (w+0.01,h+2.5) if sleeve else (w+0.01,h+0.02)
