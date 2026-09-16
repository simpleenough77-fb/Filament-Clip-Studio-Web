// Preserve the tested studio UI while routing its local API to an isolated browser worker.
(()=>{
 const nativeFetch=window.fetch.bind(window);let worker,id=0;const pending=new Map();
 const storageKey='clip-studio-web-library-v1';
 const state=()=>JSON.parse(localStorage.getItem(storageKey)||'{"version":1,"draft":null,"preferences":{},"batches":{}}');
 const request=(path,data)=>new Promise((resolve,reject)=>{
  if(!worker){worker=new Worker('./studio-worker.js?v=tested-supports-4',{type:'module'});worker.onmessage=({data:d})=>{const p=pending.get(d.id);if(!p)return;pending.delete(d.id);d.error?p.reject(Error(d.error)):p.resolve(d.value)};worker.onerror=e=>{for(const p of pending.values())p.reject(Error(e.message));pending.clear();worker.terminate();worker=null};}
  const n=++id;pending.set(n,{resolve,reject});worker.postMessage({id:n,path,data});
 });
 window.fetch=async(input,options={})=>{
  if(typeof input!=='string'||!['/catalog','/library','/csv','/review','/generate'].includes(input))return nativeFetch(input,options);
  try{
   let value;
   if(input==='/catalog'){const [cat,printers]=await Promise.all([nativeFetch('./author/Catalog.json').then(r=>r.json()),nativeFetch('./author/Printers.json').then(r=>r.json())]);value={products:cat.products,printers:Object.values(printers),fonts:['Liberation Sans:style=Bold','DejaVu Sans:style=Bold','Liberation Serif:style=Bold']};}
   else if(input==='/library'&&!options.method)value=state();
   else {const d=JSON.parse(options.body||'{}');if(input==='/library')d._state=state();value=await request(input,d);if(input==='/library')localStorage.setItem(storageKey,JSON.stringify(value));if(value.archive){value.download=URL.createObjectURL(new Blob([value.archive],{type:'application/zip'}));delete value.archive;}}
   return new Response(JSON.stringify(value),{headers:{'Content-Type':'application/json'}});
  }catch(e){return new Response(JSON.stringify({error:e.message}),{status:400,headers:{'Content-Type':'application/json'}})}
 };
})();
