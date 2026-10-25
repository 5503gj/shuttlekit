let pythonPromise;
async function runtime(){
 if(!pythonPromise)pythonPromise=(async()=>{
  postMessage({type:'status',text:'首次准备浏览器计算引擎，后续使用浏览器缓存…'});
  importScripts('./runtime/pyodide.js');
  const py=await loadPyodide({indexURL:new URL('./runtime/',self.location.href).href});
  postMessage({type:'status',text:'正在加载 NumPy、Pillow 与 OpenCV…'});
  await py.loadPackage(['numpy','pillow','opencv-python']);
  const response=await fetch('./python-source.zip');if(!response.ok)throw new Error('算法文件无法加载');
  py.FS.mkdirTree('/app');py.unpackArchive(await response.arrayBuffer(),'zip',{extractDir:'/app'});
  py.runPython("import sys;sys.path.insert(0,'/app');import browser_bridge");
  postMessage({type:'status',text:'计算引擎已就绪 · 图片与数据在浏览器内处理'});
  return py;
 })().catch(error=>{pythonPromise=null;throw error;});
 return pythonPromise;
}
let queue=Promise.resolve();
onmessage=event=>{const request=event.data;queue=queue.then(async()=>{try{const py=await runtime();if(request.action==='init'){postMessage({id:request.id,result:{ready:true}});return;}if(request.bytes){if(request.bytes.byteLength>10*1024*1024)throw new Error('文件超过10MiB');py.FS.writeFile('/app/upload.bin',new Uint8Array(request.bytes));}const safe={...request};delete safe.bytes;py.globals.set('browser_request',JSON.stringify(safe));const json=py.runPython('browser_bridge.dispatch(browser_request)');postMessage({id:request.id,result:JSON.parse(json)});}catch(error){postMessage({id:request.id,error:String(error.message||error).slice(-700)});}});};
