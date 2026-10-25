import {PythonTools} from './python-tools.js';
const status=document.getElementById('engineStatus'),retry=document.getElementById('retryEngine');
const tools=new PythonTools(message=>status.textContent=message);
let ready,serial=Promise.resolve(),queued=0,videoCancelled=false;
function initialize(){ready=tools.call('init').then(value=>{retry.hidden=true;return value;}).catch(error=>{retry.hidden=false;status.textContent='引擎加载失败，请检查网络后重试。';throw error;});ready.catch(()=>{});}
initialize();retry.onclick=()=>{if(!queued){tools.cancel();initialize();}};
function compute(action,data={}){
 if(queued>=32)return Promise.reject(new Error('操作太快，请稍候。'));
 queued++;const promise=serial.catch(()=>{}).then(async()=>{await ready;return tools.call(action,data);});serial=promise;return promise.finally(()=>queued--);
}
async function request(input,options={}){
 const url=new URL(input,location.origin),method=options.method||'GET';let body={};
 try{if(options.body)body=JSON.parse(options.body);}catch{return new Response('{"detail":"无效参数"}',{status:422});}
 if(options.signal?.aborted)throw new DOMException('已取消','AbortError');
 const token=(new Headers(options.headers).get('Authorization')||'').replace(/^Bearer /,'');
 try{
  const result=await compute('api',{path:url.pathname,method,body,token,goal:url.searchParams.get('goal')||'consistency'});
  if(options.signal?.aborted)throw new DOMException('已取消','AbortError');
  return new Response(JSON.stringify(result.body),{status:result.status,headers:{'Content-Type':'application/json'}});
 }catch(error){if(error.name==='AbortError')throw error;return new Response(JSON.stringify({detail:'浏览器计算失败，请重试加载引擎。'}),{status:503});}
}
class PageSocket{
 constructor(id){this.id=id;this.readyState=0;this.token='';queueMicrotask(()=>{this.readyState=1;this.onopen?.();});}
 send(raw){
  const event=JSON.parse(raw);if(this.readyState!==1)return;if(event.type==='auth')this.token=event.token;
  const type=event.type==='point'?'points':event.type==='reset'?'reset':'';
  request('/api/sessions/'+this.id+(type?'/'+type:''),{method:type?'POST':'GET',headers:{Authorization:'Bearer '+this.token},...(type==='points'?{body:JSON.stringify({x:event.x,y:event.y,timestamp:event.timestamp,source:event.source})}:{})})
   .then(async response=>{if(!response.ok)throw new Error('会话不可用');if(this.readyState===1)this.onmessage?.({data:JSON.stringify(await response.json())});}).catch(()=>this.onerror?.());
 }
 close(){this.readyState=3;this.onclose?.();}
}
function download(data,name){const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'})),link=document.createElement('a');link.href=url;link.download=name;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
async function exportSession(state){if(!state.sessionId){status.textContent='先创建会话再导出。';return;}const response=await request('/api/sessions/'+state.sessionId+'/coach',{headers:{Authorization:'Bearer '+state.token}});if(response.ok)download(await response.json(),'shuttlekit-trajectory.json');}
function eventOnce(target,event,action){return new Promise((resolve,reject)=>{
 const timer=setTimeout(()=>{cleanup();reject(new Error('解码超时，请换用浏览器支持的MP4或WebM。'));},10000);
 function cleanup(){clearTimeout(timer);target.removeEventListener(event,done);target.removeEventListener('error',failed);}
 function done(){cleanup();resolve();}function failed(){cleanup();reject(new Error('浏览器无法解码此视频。'));}
 target.addEventListener(event,done,{once:true});target.addEventListener('error',failed,{once:true});action?.();
});}
async function analyzeVideo(file,scaleValue){
 if(file.size>50*1024*1024)throw new Error('视频超过50MiB');
 const video=document.createElement('video');video.muted=true;video.playsInline=true;video.preload='auto';
 const url=URL.createObjectURL(file),cancel=document.getElementById('cancelVideo'),started=performance.now();videoCancelled=false;cancel.hidden=false;
 try{
  await eventOnce(video,'loadedmetadata',()=>video.src=url);
  if(!Number.isFinite(video.duration)||video.duration<=0||video.duration>60)throw new Error('请选择不超过60秒的有效视频。');
  const canvas=document.createElement('canvas'),factor=Math.min(1,1280/video.videoWidth,720/video.videoHeight);
  canvas.width=Math.max(1,Math.round(video.videoWidth*factor));canvas.height=Math.max(1,Math.round(video.videoHeight*factor));
  const context=canvas.getContext('2d',{willReadFrequently:true}),scale=scaleValue.trim()===''?null:Number(scaleValue)*factor;
  await compute('video_start',{duration:video.duration,name:file.name,scale});
  const count=Math.min(600,Math.max(1,Math.ceil(video.duration*10)));let last=-1;
  for(let i=0;i<count;i++){
   if(videoCancelled)throw new DOMException('视频分析已取消','AbortError');
   if(performance.now()-started>180000)throw new Error('视频处理超过3分钟，请缩短片段。');
   const target=Math.max(.0001,Math.min(video.duration-.0001,i/10));await eventOnce(video,'seeked',()=>video.currentTime=target);
   if(videoCancelled)throw new DOMException('视频分析已取消','AbortError');if(video.currentTime<=last)continue;last=video.currentTime;
   context.drawImage(video,0,0,canvas.width,canvas.height);
   await compute('video_frame',{timestamp:video.currentTime,frame:canvas.toDataURL('image/png').split(',')[1]});
   document.getElementById('videoStatus').textContent=`浏览器分析 ${i+1} / ${count} · ${canvas.width}×${canvas.height} · 最多10Hz`;
  }
  if(videoCancelled)throw new DOMException('视频分析已取消','AbortError');
  const report=await compute('video_finish');report.warnings.push(`原视频${video.videoWidth}×${video.videoHeight}，采样${canvas.width}×${canvas.height}；比例按${factor.toFixed(4)}同步缩放。`);return report;
 }finally{cancel.hidden=true;video.removeAttribute('src');video.load();URL.revokeObjectURL(url);await compute('video_clear').catch(()=>{});}
}
document.getElementById('cancelVideo').onclick=()=>{videoCancelled=true;document.getElementById('videoStatus').textContent='正在停止分析…';};
window.ShuttleBrowser={request,socket:id=>new PageSocket(id),exportSession,analyzeVideo};
function script(name){return new Promise((resolve,reject)=>{const tag=document.createElement('script');tag.src=new URL(name,import.meta.url).href;tag.onload=resolve;tag.onerror=reject;document.body.appendChild(tag);});}
await script('./app.js');await script('./coach.js');
document.getElementById('importTrajectory').onchange=async event=>{
 const file=event.target.files[0],message=document.getElementById('importStatus');if(!file)return;
 try{
  if(file.size>256*1024)throw new Error('轨迹JSON最大256KiB');const data=JSON.parse(await file.text()),points=data.points;
  if(!Array.isArray(points)||points.length>300||points.length<1)throw new Error('需1至300个坐标点');
  let last=-1;for(const p of points){if(![p.x,p.y,p.timestamp].every(Number.isFinite)||Math.abs(p.x)>1e9||Math.abs(p.y)>1e9||p.timestamp<=last)throw new Error('坐标或时间戳无效');last=p.timestamp;}
  const scale=data.metrics?.px_per_meter??null;if(scale!==null&&(!Number.isFinite(scale)||scale<=0||scale>1e6))throw new Error('标定比例无效');
  const created=await request('/api/sessions',{method:'POST',body:JSON.stringify({venue_id:'imported',court_id:'trajectory',fps:60,px_per_meter:scale})});if(!created.ok)throw new Error('无法创建导入会话');const session=await created.json();
  for(const point of points){const response=await request('/api/sessions/'+session.session_id+'/points',{method:'POST',headers:{Authorization:'Bearer '+session.write_token},body:JSON.stringify({x:point.x,y:point.y,timestamp:point.timestamp,source:['simulated','device','unverified'].includes(point.source)?point.source:'unverified'})});if(!response.ok)throw new Error('轨迹含无效间隔');}
  const response=await request('/api/sessions/'+session.session_id,{headers:{Authorization:'Bearer '+session.read_token}});
  window.connect({...session,...await response.json()});document.getElementById('pxPerMeter').value=scale??'';message.textContent=`已导入${points.length}个点，运行复盘可查看完整轨迹。`;
 }catch(error){message.textContent=error.message;}finally{event.target.value='';}
};
