const assert=require('node:assert/strict'),path=require('node:path'),fs=require('node:fs'),http=require('node:http');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const root=path.resolve(__dirname,'../dist'),prefix=process.env.ONLINE_PREFIX||'/demo/';
const mime={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css','.wasm':'application/wasm','.json':'application/json','.png':'image/png','.zip':'application/zip','.whl':'application/zip'};
const server=http.createServer((request,response)=>{
 let clean=decodeURIComponent(request.url.split('?')[0]);if(!clean.startsWith(prefix)){response.writeHead(404);response.end();return;}
 let filename=path.resolve(root,clean.slice(prefix.length)||'index.html');if(!filename.startsWith(root+path.sep)){response.writeHead(403);response.end();return;}
 if(fs.existsSync(filename)&&fs.statSync(filename).isDirectory())filename=path.join(filename,'index.html');
 if(!fs.existsSync(filename)){response.writeHead(404);response.end();return;}
 response.writeHead(200,{'Content-Type':mime[path.extname(filename)]||'application/octet-stream'});fs.createReadStream(filename).pipe(response);
});
async function open(){await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const browser=await chromium.launch({headless:true,...(process.env.CHROMIUM_PATH?{executablePath:process.env.CHROMIUM_PATH}:{})}),page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[],requests=[];page.setDefaultTimeout(30000);page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>requests.push({url:r.url(),method:r.method()}));page.on('response',r=>{if(r.status()>=400&&!r.url().endsWith('favicon.ico'))errors.push(r.status()+' '+r.url())});return {browser,page,errors,requests,url:`http://127.0.0.1:${server.address().port}${prefix}`,close:async()=>{await browser.close();server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}};}
module.exports={open,assert};
