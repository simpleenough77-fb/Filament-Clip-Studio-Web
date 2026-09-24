// Convert rows pasted from a spreadsheet (tab-separated) or typed CSV into the studio's import CSV.
// Kept free of DOM access so it can be tested outside the browser (tests/test_paste.mjs).
(root=>{
 const HEADER=['manufacturer','filament_type','color_name','quantity'];
 const quote=s=>'"'+String(s).replaceAll('"','""')+'"';
 // Split tab-separated text, honoring the quoting Google Sheets and Excel add around cells that contain tabs, quotes or line breaks.
 function parseTsv(text){
  const out=[];let row=[],cell='',i=0,quoted=false;
  while(i<text.length){
   const c=text[i];
   if(quoted){
    if(c==='"'&&text[i+1]==='"'){cell+='"';i+=2;continue;}
    if(c==='"'){quoted=false;i++;continue;}
    cell+=c;i++;continue;
   }
   if(c==='"'&&cell===''){quoted=true;i++;continue;}
   if(c==='\t'){row.push(cell);cell='';i++;continue;}
   if(c==='\r'){i++;continue;}
   if(c==='\n'){row.push(cell);out.push(row);row=[];cell='';i++;continue;}
   cell+=c;i++;
  }
  if(cell!==''||row.length){row.push(cell);out.push(row);}
  return out;
 }
 function pastedTextToCsv(text){
  text=String(text||'').replace(/^﻿/,'');
  if(!text.trim())throw Error('Paste at least one row first.');
  if(!text.includes('\t')){
   // Already CSV: add the header when the first line is a data row.
   const first=text.trimStart().split(/\r?\n/,1)[0].toLowerCase();
   return HEADER.every(h=>first.includes(h))?text:HEADER.join(',')+'\r\n'+text;
  }
  let rows=parseTsv(text).map(r=>r.map(c=>c.trim())).filter(r=>r.some(c=>c));
  const hasHeader=rows.length&&HEADER.every(h=>rows[0].map(c=>c.toLowerCase()).includes(h));
  if(!hasHeader)rows=[HEADER,...rows.map(r=>r.slice(0,4))];
  return rows.map(r=>r.map(quote).join(',')).join('\r\n')+'\r\n';
 }
 root.pastedTextToCsv=pastedTextToCsv;
})(typeof window!=='undefined'?window:globalThis);
