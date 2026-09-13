// PRIVATE. Accepted revision 10 geometry, unchanged.
module accepted_body(profile="Bambu Original") {
spool=profile; tunnel_alignment="Center";
// Owner-controlled parameters. All dimensions in mm.
$fn=96;
W=spool=="Cookiecad" ? 62.5 : 68;
R=100;
flange=spool=="Cookiecad" ? 5 : 3.5;
attachment_wall=spool=="Cookiecad" ? 0 : 2.5;
rim_depth=spool=="Cookiecad" ? 13 : 8;
inside_rim_radius=R-rim_depth; // Bambu 92 mm; Cookiecad 87 mm
connector_radial_height=8;
L=33;
plate_thickness=3.6;
corner_radius=1.5;
leg_thickness=2;
fit_clearance=0.25; // exploratory, not physically validated
bore=2.2; // exploratory clearance for 1.75 mm filament
outer_diameter=5;
seat_depth=2; // center depth of circular rim seat; independent of flange width
// Inset from plate side to leg outer face = flange + clearance.
leg_outer=W/2-flange-fit_clearance;
// Outward engagement in the groove; does not equal radial height.
tooth_projection=min(2.0,max(0.5,flange-attachment_wall-fit_clearance));
seat_z=plate_thickness-seat_depth;
// Fit adjustment moves the Cookiecad connector deeper without changing rim curvature.
leg_depth_adjustment=spool=="Cookiecad" ? 0.5 : 0;
tooth_top_z=seat_z+rim_depth+leg_depth_adjustment;
arc_samples=96;
edge_radius=0.35;
tip_radius=0.25;
retainer_end_radius=3; // rounds the four exposed top/end corners
tunnel_lip_radius=0.25;
tunnel_x=tunnel_alignment=="Center" ? 0 :
 (tunnel_alignment=="Left" ? -1 : 1)*(W/2-3-outer_diameter/2);
function sag(y,r)=r-sqrt(r*r-y*y);
// Radius blends at the plate perimeter; central label and rear faces stay flat.
module rounded_plate(){
 hull() for(z=concat([for(i=[0:8])edge_radius*i/8],
                    [for(i=[0:8])plate_thickness-edge_radius+edge_radius*i/8]))
 let(d=z<edge_radius ? edge_radius-z : z>plate_thickness-edge_radius ? z-(plate_thickness-edge_radius) : 0,
     inset=edge_radius-sqrt(max(0,edge_radius*edge_radius-d*d)))
 translate([0,0,min(z,plate_thickness-0.001)]) linear_extrude(0.001)
 offset(r=corner_radius-inset) square([W-2*corner_radius,L-2*corner_radius],center=true);
}
function unit2(v)=v/norm(v);
function dot2(a,b)=a.x*b.x+a.y*b.y;
function cross2(a,b)=a.x*b.y-a.y*b.x;
// Convex profile-corner fillet. Tangency is limited to leave adjacent faces intact.
function corner_arc(prev,p,next,r)=let(u=unit2(prev-p),v=unit2(next-p),
 theta=acos(max(-1,min(1,dot2(u,v)))),
 dist=min(r/tan(theta/2),0.35*min(norm(prev-p),norm(next-p))),
 rr=dist*tan(theta/2),center=p+unit2(u+v)*rr/sin(theta/2),
 start=p+u*dist-center,finish=p+v*dist-center,
 ang=atan2(start.y,start.x),sweep=atan2(cross2(start,finish),dot2(start,finish)))
 [for(k=[0:8])center+rr*[cos(ang+sweep*k/8),sin(ang+sweep*k/8)]];
function safe_profile(q)=[for(j=[0:len(q)-1]) each
 j>=3 ? corner_arc(q[(j+len(q)-1)%len(q)],q[j],q[(j+1)%len(q)],j==3?tip_radius:edge_radius) : [q[j]]];
module rim_cut(){
 for(s=[-1,1]) intersection(){
  translate([s*W/2,0,plate_thickness]) cube([2*(flange+fit_clearance),L+2,plate_thickness*2+2],center=true);
  translate([0,0,seat_z+inside_rim_radius]) rotate([0,90,0]) cylinder(h=W+2,r=inside_rim_radius,center=true,$fn=720);
 }
}
// Continuous side profile. Each Y section uses the same tooth projection
// and 8 mm radial height; the leg top follows that same spool curve.
// Flat base and plate are not warped by the connector sweep.
module raw_positive_leg_and_tooth(){
 count=30;
 verts=[for(i=[0:arc_samples]) let(
  y=-L/2+L*i/arc_samples,
  z=tooth_top_z+sag(y,inside_rim_radius),
  xi=leg_outer-leg_thickness,xo=leg_outer,
  q=safe_profile([[xi,plate_thickness-0.2],
        [xo,plate_thickness-0.2],
        [xo,z],
        [xo+tooth_projection,z+0.5],
        [xo,z+connector_radial_height],
        [xi,z+connector_radial_height]]))
  each [for(pt=q)[pt.x,y,pt.y]]];
 sides=[for(i=[0:arc_samples-1],j=[0:count-1])
  [i*count+j,i*count+(j+1)%count,(i+1)*count+(j+1)%count,(i+1)*count+j]];
 polyhedron(points=verts,faces=concat(
  [[for(j=[count-1:-1:0])j]],
  sides,
  [[for(j=[0:count-1])arc_samples*count+j]]),convexity=8);
}
// Tangent circular blends between the curved leg top and each end face.
// This trims only the two upper end corners per leg (four per clip).
module rounded_retainer_end_mask(){
 rr=retainer_end_radius;
 cy=L/2-rr;
 big_z=tooth_top_z+connector_radial_height+inside_rim_radius;
 cz=big_z-sqrt(pow(inside_rim_radius+rr,2)-cy*cy);
 tangent_y=cy*inside_rim_radius/(inside_rim_radius+rr);
 pts=concat([[-L/2,-1],[L/2,-1]],
  [for(i=[0:320]) let(y=L/2-L*i/320,ay=abs(y))
   [y,ay>tangent_y ? cz+sqrt(max(0,rr*rr-pow(ay-cy,2))) :
      tooth_top_z+connector_radial_height+sag(y,inside_rim_radius)]]);
 multmatrix([[0,0,1,0],[1,0,0,0],[0,1,0,0],[0,0,0,1]])
 linear_extrude(W+4,center=true) polygon(pts);
}
// Round vertical end corners without changing the central leg faces.
module positive_leg_and_tooth(){
 intersection(){
  raw_positive_leg_and_tooth();
  rounded_retainer_end_mask();
  translate([leg_outer-leg_thickness,-L/2,0]) linear_extrude(50)
   translate([edge_radius,edge_radius]) offset(r=edge_radius)
    square([leg_thickness+tooth_projection-2*edge_radius,L-2*edge_radius]);
 }
}
module smooth_tunnel(){
 // Rotational profile rounds both outer end lips; cylindrical middle unchanged.
 translate([tunnel_x,0,plate_thickness+outer_diameter/2-0.6]) rotate([90,0,0])
 rotate_extrude($fn=96) polygon(concat([[0,-L/2]],
 [for(i=[0:8]) let(a=-90+90*i/8)[outer_diameter/2-tunnel_lip_radius+tunnel_lip_radius*cos(a),-L/2+tunnel_lip_radius+tunnel_lip_radius*sin(a)]],
 [for(i=[0:8]) let(a=90*i/8)[outer_diameter/2-tunnel_lip_radius+tunnel_lip_radius*cos(a),L/2-tunnel_lip_radius+tunnel_lip_radius*sin(a)]],[[0,L/2]]));
}
module bore_with_rounded_entries(){
 translate([tunnel_x,0,plate_thickness+outer_diameter/2-0.6]) rotate([90,0,0])
 rotate_extrude($fn=96) polygon(concat([[0,-L/2-1],[bore/2+tunnel_lip_radius,-L/2-1]],
 [for(i=[0:8]) let(a=-90-90*i/8)[bore/2+tunnel_lip_radius+tunnel_lip_radius*cos(a),-L/2+tunnel_lip_radius+tunnel_lip_radius*sin(a)]],
 [for(i=[0:8]) let(a=180-90*i/8)[bore/2+tunnel_lip_radius+tunnel_lip_radius*cos(a),L/2-tunnel_lip_radius+tunnel_lip_radius*sin(a)]],
 [[bore/2+tunnel_lip_radius,L/2+1],[0,L/2+1]]));
}
module body(){
 difference(){
  union(){
   difference(){rounded_plate();rim_cut();}
   positive_leg_and_tooth();
   mirror([1,0,0]) positive_leg_and_tooth();
   smooth_tunnel();
  }
  bore_with_rounded_entries();
 }
}

body();
}
