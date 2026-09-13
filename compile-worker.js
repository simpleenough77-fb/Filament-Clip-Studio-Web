import OpenSCAD from './vendor/openscad/openscad.js';
self.onmessage=async({data})=>{
 let log=[];
 try{
 const m=await OpenSCAD({noInitialRun:true,print:t=>log.push(t),printErr:t=>log.push(t)});
 m.FS.mkdir('/fonts');m.FS.mkdir('/fontcache');m.FS.mkdir('/author');
 for(const f of ['LiberationSans-Bold.ttf','LiberationSerif-Bold.ttf','DejaVuSans-Bold.ttf'])m.FS.writeFile('/fonts/'+f,new Uint8Array(await(await fetch('./fonts/'+f)).arrayBuffer()));
 m.FS.writeFile('/fonts/fonts.conf','<?xml version="1.0"?><!DOCTYPE fontconfig SYSTEM "fonts.dtd"><fontconfig><dir>/fonts</dir><cachedir>/fontcache</cachedir></fontconfig>');
 m.ENV.FONTCONFIG_PATH='/fonts';m.ENV.FONTCONFIG_FILE='/fonts/fonts.conf';
 for(const f of ['Labels.scad','Accepted_Geometry.scad','bambu.stl','cookiecad.stl'])m.FS.writeFile('/author/'+f,new Uint8Array(await(await fetch('./author/'+f)).arrayBuffer()));
 m.FS.writeFile('/input.scad',data.code);
 const result=m.callMain(['/input.scad','--backend=Manifold','--enable=textmetrics','-o','/output'+data.ext]);
 if(result!==0||log.some(l=>/^ERROR:/.test(l)))throw Error(log.join('\n'));
 const bytes=m.FS.readFile('/output'+data.ext);
 self.postMessage({ok:true,log:log.join('\n'),bytes},[bytes.buffer]);
 }catch(e){self.postMessage({ok:false,error:String(e),log:log.join('\n')})}
};
