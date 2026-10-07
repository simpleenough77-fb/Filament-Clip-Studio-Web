"""Sleeve support data: manual support paint and the tunnel blocker.

An STL cannot hold support paint, so the paint the owner applied in the tested sleeve projects is described as rules and
applied to every vendor's sleeve body (the tunnel and the sleeve bar are the same design on every clip):

* enforcer (paint code 4): the flat underside of the sleeve bar between the legs, so it is supported;
* blocker (paint code 8): the surface of the filament bore along its middle, so no support grows inside the tunnel.

A 4 mm cylinder (a support-blocker part) also runs the length of the tunnel.
"""
import math
import nfc

ENFORCER='4'
BLOCKER='8'
BLOCKER_D=4.0       # keeps support out of the 2.2 mm filament bore
BORE_AXIS_Z=5.5     # height of the bore axis above the front face
BORE_RADIUS=1.2     # bore is 2.2 mm across; painted faces sit just inside it
BORE_HALF_LENGTH=5.6  # short bore faces are painted along this middle stretch ...
BORE_LONG_FACE=12.0   # ... and a face that runs the length of the tunnel is painted whole
BAR_Z=(9.0,12.0)    # underside of the sleeve bar lies in this height band
BLOCKER_Z=5.6       # axis height of the blocker cylinder
BLOCKER_PAD=1.0     # blocker runs this far past each end of the clip

def support_paint(vertices,faces,leg_inner):
    """paint_supports code (or '') for each face of a sleeve body in the centred clip frame."""
    flags=[]
    for f in faces:
        a,b,c=[vertices[i] for i in f]
        ux,uy,uz=b[0]-a[0],b[1]-a[1],b[2]-a[2];vx,vy,vz=c[0]-a[0],c[1]-a[1],c[2]-a[2]
        nx,ny,nz=uy*vz-uz*vy,uz*vx-ux*vz,ux*vy-uy*vx;ln=math.sqrt(nx*nx+ny*ny+nz*nz)
        code=''
        if ln>1e-12:
            nx,ny,nz=nx/ln,ny/ln,nz/ln
            cx,cy,cz=(a[0]+b[0]+c[0])/3,(a[1]+b[1]+c[1])/3,(a[2]+b[2]+c[2])/3
            if nz<-0.99 and BAR_Z[0]<=cz<=BAR_Z[1] and abs(cx)<=leg_inner-1:code=ENFORCER
            elif abs(ny)<0.3 and math.hypot(cx,cz-BORE_AXIS_Z)<=BORE_RADIUS and (abs(cy)<=BORE_HALF_LENGTH or max(a[1],b[1],c[1])-min(a[1],b[1],c[1])>=BORE_LONG_FACE):code=BLOCKER
        flags.append(code)
    return flags

def tunnel_blocker(height):
    """Support-blocker cylinder along the tunnel (Y axis), `height` being the clip's Y size."""
    verts,faces=nfc.cylinder_mesh([(0.0,0.0)],-(height/2+BLOCKER_PAD),height/2+BLOCKER_PAD,BLOCKER_D,48)
    # cylinder_mesh runs along Z; turn it to run along Y (swapping two axes mirrors it, so flip the winding back)
    verts=[(x,z,y+BLOCKER_Z) for x,y,z in verts];faces=[[a,c,b] for a,b,c in faces]
    return verts,faces

def sleeve_parts(spec,body_mesh):
    """(paint flags for the body, blocker part) for a sleeve body."""
    vertices,faces=body_mesh
    return support_paint(vertices,faces,spec['leg_inner']),('Tunnel support blocker',tunnel_blocker(spec['size'][1]))
