// Inland cardboard spool clip - unsleeved prototype
// Dimensions supplied by owner, October 2026.
$fn=96;
plate_w=61;                 // clear inside width
plate_l=53;                 // spans the 40 mm hole spacing with margins
plate_t=3.6;
corner_r=3;
spool_od=200;
flange_od=67;
flange_id=61;
flange_t=3;
hole_d=6;
hole_spacing=40;            // along the flange curve; prototype uses chord spacing
rim_offset=9;               // hole center in from outside edge
pin_d=4;
pin_len=3.5;
pin_clearance=0.25;
// Hole center from the clip centerline: half flange OD minus rim offset.
pin_x=flange_od/2-rim_offset; // 24.5 mm
// Shallow underside side relief follows the inner rim; intentionally symmetric.
inside_r=92;
relief_depth=3;
relief_r=inside_r;
module rounded_plate(){
  linear_extrude(plate_t)
    offset(r=corner_r)
      square([plate_w-2*corner_r,plate_l-2*corner_r],center=true);
}
module underside_rim_relief(){
  // Keep the label face and center flat; remove only the two side bands.
  for (s=[-1,1]) intersection(){
    translate([s*(plate_w/2-2),0,-0.01])
      cube([4,plate_l+2,relief_depth+0.02],center=true);
    translate([0,0,plate_t-relief_depth+relief_r])
      rotate([0,90,0]) cylinder(h=plate_w+4,r=relief_r,center=true);
  }
}
module pin(x,y){
  // Pins project from the underside into the cardboard flange holes.
  // Keep 0.25 mm of overlap inside the plate while leaving the full
  // specified 3.5 mm exposed below it.
  translate([x,y,-pin_len])
    cylinder(h=pin_len+pin_clearance,r=pin_d/2);
}
difference(){
  union(){
    difference(){rounded_plate(); underside_rim_relief();}
    for (x=[-pin_x,pin_x]) for (y=[-hole_spacing/2,hole_spacing/2]) pin(x,y);
  }
}
