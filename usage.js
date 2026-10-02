// Anonymous usage count: after a batch is generated, send totals (clip count, vendor mix, printer, option flags).
// Never sends label text, filenames, CSV contents or anything that identifies the visitor.
// Fire-and-forget: a failure here must never affect generating or downloading.
window.reportUsage=function(review){
 try{
  const vendors={};
  for(const r of rows){const m=product(r.product)?.manufacturer;if(m)vendors[m]=(vendors[m]||0)+r.quantity;}
  const s=settings();
  const body={
   clips:rows.reduce((n,r)=>n+r.quantity,0),
   holders:(review?.accessories||[]).reduce((n,a)=>n+(a.quantity||0),0),
   plates:review?.plates?.length||0,
   printer:s.printer,
   nfc:s.nfc==='yes',
   sleeve:s.holder_sleeve==='yes',
   vendors
  };
  fetch('/api/stat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),keepalive:true}).catch(()=>{});
 }catch{}
};
