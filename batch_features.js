let savedLibrary={},undoDraft=null,saveQueue=Promise.resolve(),saveTimer;
const clone=x=>JSON.parse(JSON.stringify(x));
function draft(){return {rows:clone(rows),settings:settings()};}
function persistDraft(){
 const data=draft();
 try{localStorage.setItem('clip-label-draft',JSON.stringify(data));}catch{$('libraryStatus').textContent='Browser storage is unavailable; download a CSV backup to keep your work.';}
 clearTimeout(saveTimer);saveTimer=setTimeout(()=>queueSave(data),400);
}
function queueSave(data){
 saveQueue=saveQueue.catch(()=>{}).then(()=>api('/library',{action:'draft',draft:data})).then(()=>{$('libraryStatus').textContent='Draft and preferences saved on this computer.';}).catch(e=>{$('libraryStatus').textContent='Draft not saved: '+e.message;});return saveQueue;
}
function applyDraft(d){
 if(!d||!Array.isArray(d.rows)||d.rows.some(r=>!product(r.product)))throw Error('This batch includes a filament no longer available in the catalog. Your current batch was kept.');
 if(d.rows.some(r=>!Number.isInteger(r.quantity)||r.quantity<1)||d.rows.reduce((n,r)=>n+r.quantity,0)>100)throw Error('Batch quantities must be whole numbers, with no more than 100 clips.');
 rows=clone(d.rows);
 for(const k of ['printer','font','type_size','vendor_size','color_size','style','body_mode','text_mode']){
  if(d.settings?.[k]!==undefined){const el=$(k),v=String(d.settings[k]);if(el.tagName!=='SELECT'||[...el.options].some(o=>o.value===v))el.value=v;}
 }
 renderRows();
}
function rememberUndo(){undoDraft=draft();try{localStorage.setItem('clip-label-undo',JSON.stringify(undoDraft));}catch{}}
function renderLibrary(){
 const selected=$('savedBatch').value;
 $('savedBatch').innerHTML='<option value="">Choose a saved batch</option>'+Object.entries(savedLibrary).sort((a,b)=>a[1].name.localeCompare(b[1].name)).map(([k,v])=>`<option value="${esc(k)}">${esc(v.name)} · ${v.draft.rows.reduce((n,r)=>n+r.quantity,0)} clips</option>`).join('');
 $('savedBatch').value=selected;
}
$('saveBatch').onclick=()=>busy('Saving batch…',async()=>{
 clearTimeout(saveTimer);await saveQueue;
 const state=await api('/library',{action:'batch',name:$('batchName').value,draft:draft()});savedLibrary=state.batches;renderLibrary();$('savedBatch').value=$('batchName').value.trim().toLowerCase();$('libraryStatus').textContent='Named batch saved. Earlier versions are retained in the local library.';
});
$('loadBatch').onclick=()=>busy('Opening batch…',async()=>{
 const entry=savedLibrary[$('savedBatch').value];if(!entry)throw Error('Choose a saved batch first.');
 const before=draft();applyDraft(entry.draft);undoDraft=before;try{localStorage.setItem('clip-label-undo',JSON.stringify(before));}catch{}
 $('batchName').value=entry.name;invalidate();
});
$('newBatch').onclick=()=>{rememberUndo();rows=[];$('batchName').value='';$('savedBatch').value='';invalidate();renderRows();};
$('undoBatch').onclick=()=>busy('Restoring previous batch…',async()=>{
 let previous=undoDraft;try{previous=previous||JSON.parse(localStorage.getItem('clip-label-undo')||'null');}catch{}
 if(!previous)throw Error('There is no previous batch change to undo.');
 let current=draft();applyDraft(previous);undoDraft=current;try{localStorage.setItem('clip-label-undo',JSON.stringify(current));}catch{}invalidate();
});
function mergedRows(input){
 let result=[],map=new Map();
 for(const row of input){let key=JSON.stringify([row.product,row.swatch||product(row.product)?.swatch]);if(map.has(key))map.get(key).quantity+=row.quantity;else{let copy=clone(row);map.set(key,copy);result.push(copy);}}
 if(result.some(r=>!Number.isInteger(r.quantity)||r.quantity<1)||result.reduce((n,r)=>n+r.quantity,0)>100)throw Error('Use whole quantities and no more than 100 clips per batch.');
 return result;
}
$('merge').onclick=()=>busy('Merging duplicates…',async()=>{let next=mergedRows(rows),count=rows.length-next.length;rememberUndo();rows=next;invalidate();renderRows();$('importReport').textContent=`Merged ${count} duplicate row${count===1?'':'s'}. Clip quantities are unchanged.`;});
function csvForRows(input){const quote=s=>'"'+String(s).replaceAll('"','""')+'"';return '\uFEFF'+[['manufacturer','filament_type','color_name','quantity'],...input.map(r=>{let p=product(r.product);return [p.manufacturer,p.filament_type,p.color_name,r.quantity];})].map(r=>r.map(quote).join(',')).join('\r\n')+'\r\n';}
$('exportCsv').onclick=()=>busy('Preparing CSV…',async()=>{
 if(!rows.length)throw Error('Add at least one label before downloading CSV.');mergedRows(rows);
 const url=URL.createObjectURL(new Blob([csvForRows(rows)],{type:'text/csv;charset=utf-8'}));let a=document.createElement('a');a.href=url;a.download=($('batchName').value.trim().replace(/[^\p{L}\p{N} _-]/gu,'-')||'Labels')+'.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
});
async function importText(text){
 const mode=$('importMode').value,d=await api('/csv',{csv:text,mode,existing:rows});
 if(d.rows.length){let next=mergedRows(mode==='add'?[...rows,...d.rows]:d.rows);rememberUndo();rows=next;invalidate();renderRows();}
 $('importReport').innerHTML=`<p>${d.imported} CSV records imported (${d.total} clips ${mode==='add'?'added':'loaded'}). ${d.skipped.length} records skipped. Current batch: ${rows.reduce((n,r)=>n+r.quantity,0)} clips.${!d.rows.length?' Your existing batch was kept.':''}</p>`+(d.skipped.length?`<div class="scroll-table"><table><thead><tr><th>CSV row</th><th>Manufacturer</th><th>Type</th><th>Color / name</th><th>Quantity</th><th>Reason</th></tr></thead><tbody>${d.skipped.map(r=>`<tr><td>${r.row}</td><td>${esc(r.manufacturer)}</td><td>${esc(r.filament_type)}</td><td>${esc(r.color_name)}</td><td>${esc(r.quantity)}</td><td>${esc(r.reason)}</td></tr>`).join('')}</tbody></table></div>`:'');
}
$('import').onclick=()=>$('file').click();$('file').onchange=()=>busy('Reading CSV…',async()=>{try{if($('file').files.length)await importText(await $('file').files[0].text());}finally{$('file').value='';}});
async function refreshExcel(){
 try{let d=await fetch('/excel-exports').then(r=>r.json());$('excelFile').innerHTML=d.files.length?d.files.map(f=>`<option value="${esc(f.name)}">${esc(new Date(f.modified*1000).toLocaleString())} · ${esc(f.name)}</option>`).join(''):'<option value="">No Excel exports yet</option>';excelSelection();}catch{$('excelFile').innerHTML='<option value="">Excel exports unavailable</option>';excelSelection();}
}
function excelSelection(){let name=$('excelFile').value;$('downloadExcel').classList.toggle('hidden',!name);$('downloadExcel').href='/excel-csv/'+encodeURIComponent(name);$('downloadExcel').download=name;}
$('excelFile').onchange=excelSelection;$('refreshExcel').onclick=refreshExcel;
$('importExcel').onclick=()=>busy('Reading Excel CSV…',async()=>{let name=$('excelFile').value;if(!name)throw Error('Export a CSV from the workbook first, then refresh this list.');let r=await fetch('/excel-csv/'+encodeURIComponent(name));if(!r.ok)throw Error('That Excel export is unavailable. Refresh the list.');await importText(await r.text());});

Promise.all([fetch('/catalog').then(r=>r.json()),fetch('/library').then(r=>r.json())]).then(([d,library])=>{
 catalog=d.products;fonts=d.fonts;$('printer').innerHTML=d.printers.map(p=>`<option value="${esc(p.id)}">${esc(p.label)}</option>`).join('');$('font').innerHTML=options(fonts,fonts[0]);
 rows=[catalog.find(p=>p.color_name==='Blue'&&p.manufacturer==='Bambu Lab'),catalog.find(p=>p.color_name==='Dark Magic'&&p.filament_type==='PLA')].map(p=>({product:p.id,quantity:1,swatch:p.swatch}));
 let saved;try{saved=JSON.parse(localStorage.getItem('clip-label-draft')||'null');}catch{}
 saved=saved||library.draft||d.draft;
 if(saved)applyDraft(saved);else renderRows();
 savedLibrary=library.batches||{};renderLibrary();persistDraft();
}).catch(e=>$('error').textContent='Unable to load the catalog or saved batches: '+e.message);
