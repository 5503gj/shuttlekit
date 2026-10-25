/* Mirror only immutable Pyodide assets. Input images and project files never enter this path. */
(function(root,factory){if(typeof module==='object'&&module.exports)module.exports=factory();else root.createRuntimeFetch=factory();})(typeof self!=='undefined'?self:globalThis,()=>{
 return function createRuntimeFetch({siteBase,acceleratedBase,nativeFetch,accelerated,onFallback=()=>{},timeout=30000}){
  return async function(input,options={}){
   const address=typeof input==='string'?input:input.url||String(input);
   if(!accelerated||!address.startsWith(siteBase))return nativeFetch(input,options);
   const primary=acceleratedBase+address.slice(siteBase.length),controller=new AbortController(),timer=setTimeout(()=>controller.abort(),timeout);
   const abort=()=>controller.abort();options.signal?.addEventListener('abort',abort,{once:true});
   try{
    if(options.signal?.aborted)throw new DOMException('Aborted','AbortError');
    const response=await nativeFetch(primary,{...options,mode:'cors',credentials:'omit',signal:controller.signal});
    if(!response.ok)throw new Error('Runtime mirror unavailable');
    const bytes=await response.arrayBuffer();
    return new Response(bytes,{status:response.status,headers:{'Content-Type':response.headers.get('Content-Type')||'application/octet-stream'}});
   }catch(error){
    if(options.signal?.aborted)throw error;
    onFallback();return nativeFetch(input,options);
   }finally{clearTimeout(timer);options.signal?.removeEventListener('abort',abort);}
  };
 };
});
