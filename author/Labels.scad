// PRIVATE label layout. Measurements and geometry use the same OpenSCAD font.
function label_prefix(t,n)=n<=0?"":str(label_prefix(t,n-1),t[n-1]);
function label_width(t,size,font)=textmetrics(t,size=size,font=font).size.x;
function label_shorten(t,size,font,width,n)=n<=0?".":
 label_width(str(label_prefix(t,n),"."),size,font)<=width?
 str(label_prefix(t,n),"."):label_shorten(t,size,font,width,n-1);
function label_fit(t,size,font,width)=label_width(t,size,font)<=width?t:label_shorten(t,size,font,width,len(t)-1);
module glyph(t,size,font,width,depth=.6){
 fitted=label_fit(t,size,font,width);
 m=textmetrics(fitted,size=size,font=font);
 assert(m.size.x<=width,"Font too large even for ellipsis.");
 assert(m.size.y<=8,"Text too tall; reduce the selected font size.");
 // Face looks outward toward -Z; mirror Y for correctly readable front text.
 linear_extrude(depth) mirror([0,1,0])
 translate([-m.position.x-m.size.x/2,-m.position.y-m.size.y/2])
 text(fitted,size=size,font=font);
}
module label_line(lines,sizes,font,width,index,depth=.6){
 translate([0,(index-1)*9,0]) glyph(lines[index],sizes[index],font,width,depth);
}
module label_all(lines,sizes,font,width,depth=.6){
 for(i=[0:2])label_line(lines,sizes,font,width,i,depth);
}
