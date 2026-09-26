import {loadPyodide} from './vendor/pyodide/pyodide.mjs';
const python=loadPyodide({indexURL:new URL('./vendor/pyodide/',import.meta.url).href}).then(async py=>{
 await py.loadPackage('pillow');
 const assets=await(await fetch('./assets.json?v=tested-supports-6')).json();
 py.FS.mkdir('/author');py.FS.mkdir('/Generated');py.FS.mkdir('/.cache');
 for(const name of assets){const path='/'+name;py.FS.mkdirTree(path.slice(0,path.lastIndexOf('/')));py.FS.writeFile(path,new Uint8Array(await(await fetch('./'+name+'?v=tested-supports-6')).arrayBuffer()));}
 await py.runPythonAsync('import sys\nsys.path.insert(0,"/author")\nimport generator as g\nimport json,base64\n');
 return py;
});
self.compileScad=(code,ext)=>new Promise((resolve,reject)=>{
 const w=new Worker('./compile-worker.js?v=tested-supports-6',{type:'module'});
 const timer=setTimeout(()=>{w.terminate();reject(Error('A clip took too long to generate. Try a smaller batch.'));},120000);
 w.onmessage=({data})=>{clearTimeout(timer);w.terminate();if(!data.ok)return reject(Error(data.error));let s='';for(let i=0;i<data.bytes.length;i+=32768)s+=String.fromCharCode(...data.bytes.subarray(i,i+32768));resolve(JSON.stringify({bytes:btoa(s),log:data.log}));};
 w.onerror=e=>{clearTimeout(timer);w.terminate();reject(Error(e.message))};w.postMessage({code,ext});
});
let queue=Promise.resolve();
self.onmessage=({data:{id,path,data}})=>{queue=queue.catch(()=>{}).then(async()=>{
 try{const py=await python;py.globals.set('payload',JSON.stringify(data));let code;
 if(path==='/review')code='g.PREFLIGHTS.clear()\njson.dumps(await g.preflight(json.loads(payload)))';
 else if(path==='/generate')code='json.dumps(await g.generate(**json.loads(payload)))';
 else if(path==='/csv')code=`d=json.loads(payload)\nexisting=g.validate(dict(rows=d.get('existing'),settings={}))['rows'] if d.get('mode')=='add' and d.get('existing') else []\nresult=g.import_csv(d.get('csv',''),100-sum(r['quantity'] for r in existing))\njson.dumps(result)`;
 else if(path==='/library')code=`d=json.loads(payload)\ng.LIBRARY.write_text(json.dumps(d.pop('_state')))\njson.dumps(g.batch_library.update(g.LIBRARY,d,g.validate))`;
 else throw Error('Unknown operation');
 const value=JSON.parse(await py.runPythonAsync(code));
 if(path==='/generate'){const file=value.download.split('/').pop();const bytes=py.FS.readFile('/Generated/'+file);await py.runPythonAsync("import shutil\nshutil.rmtree(g.GENERATED)\ng.GENERATED.mkdir()\nshutil.rmtree(g.CACHE)\ng.CACHE.mkdir()");value.archive=bytes;delete value.download;self.postMessage({id,value},[bytes.buffer]);}
 else self.postMessage({id,value});
 }catch(e){self.postMessage({id,error:String(e.message||e)})}
 });};
