const state = { sessionId: null, socket: null, history: [], token:null, readToken:null, readOnly:false };
const apiRequest=(...args)=>window.ShuttleBrowser?window.ShuttleBrowser.request(...args):fetch(...args);
const $ = (id) => document.getElementById(id);

function setBadge(text, online) { const badge = $("connectionBadge"); badge.textContent = text; badge.className = `badge ${online ? "badge-online" : "badge-offline"}`; }
function render(data) {
  state.snapshot=data;
  if(data.quality==="reset"){state.history=[];state.chartTimestamp=null;}
  $("chartUnit").textContent=data.px_per_meter==null?`未标定 · 当前 ${Number(data.current_speed_px_s||0).toFixed(1)} px/s`:'km/h · 2D比例估计';
  $("currentSpeed").textContent = data.current_speed_kmh == null ? '—' : Number(data.current_speed_kmh).toFixed(1);
  $("peakSpeed").textContent = data.peak_speed_kmh == null ? '—' : Number(data.peak_speed_kmh).toFixed(1);
  $("averageSpeed").textContent = data.average_speed_kmh == null ? '—' : Number(data.average_speed_kmh).toFixed(1);
  $("sampleCount").textContent = data.sample_count || 0;
  $("qualityLabel").textContent = data.quality === "outlier" ? "已过滤异常点" : data.status === "tracking" ? "追踪中" : "等待数据";
  $("lastUpdate").textContent = `最后更新 ${new Date().toLocaleTimeString()}`;
  if (data.last_point && data.quality !== "outlier" && data.last_point.speed_kmh!=null && state.chartTimestamp!==data.last_point.timestamp) { state.history.push(Number(data.last_point.speed_kmh)); state.history = state.history.slice(-30);state.chartTimestamp=data.last_point.timestamp; }
  window.dispatchEvent(new CustomEvent('shuttle-state',{detail:data}));
  drawChart();
}
function drawChart() {
  const canvas = $("speedChart"), ctx = canvas.getContext("2d"), w = canvas.width, h = canvas.height;
  ctx.clearRect(0, 0, w, h); ctx.strokeStyle = "#e0e8e0"; ctx.lineWidth = 1;
  for (let i = 1; i < 5; i++) { const y = (h / 5) * i; ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke(); }
  if (!state.history.length) return;
  const max = Math.max(360, ...state.history) * 1.08, step = w / Math.max(1, state.history.length - 1);
  ctx.beginPath(); state.history.forEach((speed, i) => { const x = i * step, y = h - speed / max * (h - 20) - 10; i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); });
  ctx.lineTo((state.history.length - 1) * step, h); ctx.lineTo(0, h); ctx.closePath(); ctx.fillStyle = "#d7f46b88"; ctx.fill();
  ctx.beginPath(); state.history.forEach((speed, i) => { const x = i * step, y = h - speed / max * (h - 20) - 10; i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); }); ctx.strokeStyle = "#1c7c56"; ctx.lineWidth = 4; ctx.stroke();
}
function closeSocket() { if (state.socket) { state.socket.close(); state.socket = null; } }
function connect(session) {
  closeSocket(); state.history = []; state.sessionId = session.session_id; state.token=session.write_token||session.read_token;state.readToken=session.read_token;state.readOnly=!session.write_token;
  const protocol = location.protocol === "https:" ? "wss" : "ws";
  state.socket = window.ShuttleBrowser?window.ShuttleBrowser.socket(state.sessionId):new WebSocket(`${protocol}://${location.host}/ws/sessions/${state.sessionId}`);
  const socket=state.socket;state.chartTimestamp=null;
  state.socket.onopen = () => { state.socket.send(JSON.stringify({type:"auth",token:state.token}));setBadge(window.ShuttleBrowser?"浏览器会话已就绪":state.readOnly?"只读显示已连接":"采集端已连接",true); };
  state.socket.onclose = () => setBadge("连接已断开", false);
  state.socket.onerror = () => setBadge("连接异常", false);
  state.socket.onmessage = (event) => { if(state.socket!==socket)return;const data = JSON.parse(event.data); if (!data.error) render(data); };
  $("sessionLabel").textContent = `${session.venue_id} / ${session.court_id} · ${session.session_id}`;
  $("resetBtn").disabled = state.readOnly; document.querySelectorAll(".shot-button").forEach(b=>b.disabled=state.readOnly); render(session);
}
async function createSession() {
  const body = { venue_id: $("venueId").value.trim(), court_id: $("courtId").value.trim(), fps: Number($("fps").value), px_per_meter: $("pxPerMeter").value.trim()===''?null:Number($("pxPerMeter").value) };
  if (!body.venue_id || !body.court_id) return alert("请填写球馆 ID 和场地 ID");
  const response = await apiRequest("/api/sessions", { method: "POST", headers: { "Content-Type": "application/json",...adminHeaders() }, body: JSON.stringify(body) });
  if (!response.ok) return alert("创建会话失败，请检查参数"); connect(await response.json());
}
function sendPoint(x, y, timestamp) { if(state.readOnly)return; if (!state.socket || state.socket.readyState !== WebSocket.OPEN) return alert("请先创建并连接实时会话"); state.socket.send(JSON.stringify({ type: "point", x, y, timestamp,source:'simulated' })); }
async function simulateShot(targetSpeed) {
  if (!state.sessionId || state.readOnly || state.simulating) return;
  const sessionId=state.sessionId;state.simulating=true;
  try {
  const reset=await apiRequest('/api/sessions/'+sessionId+'/reset',{method:'POST',headers:{Authorization:'Bearer '+state.token}});
  if(!reset.ok)throw new Error('重置失败，请重新连接');
  const pxPerMeter = Number($("pxPerMeter").value) || 50, interval = 80, distance = targetSpeed / 3.6 * pxPerMeter * interval / 1000, start = performance.now() / 1000;
  for (let i = 0; i < 8; i++) { if(state.sessionId!==sessionId)return;sendPoint(i * distance, 180 + Math.sin(i * .8) * 12, start + i * interval / 1000); await new Promise((resolve) => setTimeout(resolve, 80)); }
  }catch(error){alert(error.message)}finally{state.simulating=false}
}
function renderVideoReport(report) {
  $("videoResult").classList.remove("hidden");
  $("videoShotType").textContent = report.shot_type || "数据不足";
  $("videoConfidence").textContent = "阈值参考，非校准概率";
  $("videoPeak").textContent = report.peak_speed_kmh == null ? (report.peak_speed_px_s == null ? '数据不足' : `${Number(report.peak_speed_px_s).toFixed(1)} px/s`) : `${Number(report.peak_speed_kmh).toFixed(1)} km/h`;
  $("videoAverage").textContent = report.average_speed_kmh == null ? '未标定/数据不足' : `${Number(report.average_speed_kmh).toFixed(1)} km/h`;
  $("videoAngle").textContent = report.trajectory_angle_deg == null ? '数据不足' : `${Number(report.trajectory_angle_deg).toFixed(1)}°（画面）`;
  const court = report.court || {};
  $("videoCourtSize").textContent = "实际场地尺寸未测量";
  $("videoDetectionRate").textContent = `${Math.round(Number(report.detection_rate || 0) * 100)}%`;
  $("videoCalibration").textContent = court.px_per_meter == null ? '未标定，仅px/s' : `${court.px_per_meter} px/m · 人工输入（2D投影估计）`;
  const warnings = $("videoWarnings"); warnings.innerHTML = "";
  (report.warnings || []).forEach((warning) => { const item = document.createElement("li"); item.textContent = warning; warnings.appendChild(item); });
  // Video results have their own report; keep the live chart tied to its session.
  saveVideoHistory(report);
}
function loadVideoHistory() { try { const rows=JSON.parse(localStorage.getItem("shuttlekit.videoHistory") || "[]");return Array.isArray(rows)?rows.filter(row=>row&&Number.isFinite(row.peak)&&Number.isFinite(row.average)).slice(0,20):[]; } catch (error) { return []; } }
function saveVideoHistory(report) {
  if(report.peak_speed_kmh == null || report.average_speed_kmh==null)return; const records = loadVideoHistory(); records.unshift({ at: new Date().toISOString(), shot:String(report.shot_type||'未知'), peak: Number(report.peak_speed_kmh), average: Number(report.average_speed_kmh), angle: report.trajectory_angle_deg??null });
  try{localStorage.setItem("shuttlekit.videoHistory", JSON.stringify(records.slice(0, 20)));renderVideoHistory();}catch{$("videoStatus").textContent='结果已生成；本机存储不可用，摘要未保存。';}
}
function renderVideoHistory() {
  const records = loadVideoHistory(), list = $("historyList"), empty = $("historyEmpty");
  $("historySummary").textContent = `${records.length} 次视频 · 最佳 ${records.length ? Math.max(...records.map((item) => item.peak)).toFixed(1) : "0.0"} km/h`;
  empty.classList.toggle("hidden", records.length > 0); list.innerHTML = "";
  records.slice(0, 8).forEach((item) => { const row = document.createElement("div");row.className='history-item';for(const text of [new Date(item.at).toLocaleString(),`${item.peak.toFixed(1)} km/h`,`均值 ${item.average.toFixed(1)}`,Number.isFinite(item.angle)?`画面角 ${item.angle.toFixed(1)}°`:'画面角未知',item.shot]){const span=document.createElement('span');span.textContent=text;row.appendChild(span);}list.appendChild(row); });
}
function shareVideoResult() {
  const canvas = document.createElement("canvas"); canvas.width = 1000; canvas.height = 560; const ctx = canvas.getContext("2d");
  ctx.fillStyle = "#113e2d"; ctx.fillRect(0, 0, canvas.width, canvas.height); ctx.fillStyle = "#d7f46b"; ctx.font = "700 30px sans-serif"; ctx.fillText("SHUTTLEKIT / SMASH RESULT", 60, 70);
  ctx.fillStyle = "#ffffff"; ctx.font = "800 76px sans-serif"; ctx.fillText($("videoShotType").textContent, 60, 180); ctx.fillStyle = "#d7f46b"; ctx.font = "800 92px sans-serif"; ctx.fillText($("videoPeak").textContent, 60, 310);
  ctx.fillStyle = "#d9f1dd"; ctx.font = "28px sans-serif"; ctx.fillText(`角度 ${$("videoAngle").textContent}   平均 ${$("videoAverage").textContent}`, 60, 385); ctx.fillText(`置信度 ${$("videoConfidence").textContent.replace("置信度 ", "")}`, 60, 440); ctx.fillStyle = "#ffffff99"; ctx.font = "20px sans-serif"; ctx.fillText("视频分析结果 · 仅供训练参考", 60, 510);
  canvas.toBlob((blob) => { const link = document.createElement("a"); link.download = "shuttlekit-smash-result.png"; link.href = URL.createObjectURL(blob); link.click(); URL.revokeObjectURL(link.href); });
}
async function analyzeVideo() {
  const file = $("videoFile").files[0];
  if (!file) return alert("请先选择一段视频");
  const button = $("analyzeVideoBtn"); button.disabled = true; $("videoStatus").textContent = `正在分析 ${file.name}…`;
  const form = new FormData(); form.append("file", file); const scale=$("videoScale").value;if(scale)form.append("px_per_meter",scale);
  try {
    if(window.ShuttleBrowser){const result=await window.ShuttleBrowser.analyzeVideo(file,scale);renderVideoReport(result);$("videoStatus").textContent=`浏览器分析完成 · ${result.total_frames}个采样帧 · ${result.duration_s}s`;return;}
    const response = await apiRequest("/api/video/analyze", { method: "POST", headers:adminHeaders(), body: form });
    const payload = await response.json(); if (!response.ok) throw new Error(payload.detail || "视频分析失败");
    renderVideoReport(payload); $("videoStatus").textContent = `分析完成 · ${payload.total_frames} 帧 · ${payload.duration_s}s`;
  } catch (error) { $("videoStatus").textContent = error.message; alert(error.message); }
  finally { button.disabled = false; }
}
function formatEquipmentPrice(item) { return item.price_min != null && item.price_max != null ? `${item.price_min}-${item.price_max} 元` : "价格以实际渠道为准"; }
function renderEquipmentResults(payload) {
  const container = $("equipmentResults"); container.innerHTML = "";
  if (!payload.results?.length) { container.innerHTML = '<div class="history-empty">当前画像暂无匹配结果。</div>'; return; }
  payload.results.forEach((match) => { const item=match.item,card=document.createElement('div');card.className='equipment-card';for(const [tag,cls,text] of [['h4','',`${item.brand||''} ${item.model||''}`],['div','equip-meta',`规则匹配 ${Number(match.score||0).toFixed(0)} · 样本评分 ${item.rating||'—'}`],['div','equip-price',formatEquipmentPrice(item)],['div','equip-reasons',`${(match.reasons||[]).join(' · ')} · ${Object.entries(item.specs||{}).map(([k,v])=>`${k}: ${v}`).join(' · ')}`],['div','equip-source',`来源：${item.source||'未标注'}`]]){const node=document.createElement(tag);node.className=cls;node.textContent=text;card.appendChild(node);}container.appendChild(card); });
}
async function recommendEquipment() {
  const payload = { category: $("equipmentCategory").value, level: $("equipmentLevel").value, budget: Number($("equipmentBudget").value), play_style: $("equipmentStyle").value, gender: "不限", top_k: 6 };
  const button = $("recommendEquipmentBtn"); button.disabled = true; $("equipmentResults").innerHTML = '<div class="history-empty">正在匹配装备…</div>';
  try { const response = await apiRequest("/api/equipment/recommend", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }); const data = await response.json(); if (!response.ok) throw new Error(typeof data.detail==='string'?data.detail:"请检查预算与画像参数"); renderEquipmentResults(data); } catch (error) { $("equipmentResults").textContent=error.message; } finally { button.disabled = false; }
}
async function loadEquipmentStats() { try { const response = await apiRequest("/api/equipment/stats"); const data = await response.json(); $("equipmentStats").textContent = `${data.total} 款样本 · 非实时爬取`; } catch (error) { $("equipmentStats").textContent = "装备库离线"; } }
$("createBtn").addEventListener("click", createSession);
$("resetBtn").addEventListener("click", () => { if (state.socket?.readyState === WebSocket.OPEN) state.socket.send(JSON.stringify({ type: "reset" })); state.history = []; });
document.querySelectorAll(".shot-button").forEach((button) => button.addEventListener("click", () => simulateShot(Number(button.dataset.speed))));
$("videoFile").addEventListener("change", () => { const file = $("videoFile").files[0]; $("videoStatus").textContent = file ? `${file.name} · 准备上传` : "尚未选择视频"; });
$("analyzeVideoBtn").addEventListener("click", analyzeVideo);
$("shareVideoBtn").addEventListener("click", shareVideoResult);
$("recommendEquipmentBtn").addEventListener("click", recommendEquipment);
window.addEventListener("resize", drawChart); drawChart(); renderVideoHistory(); loadEquipmentStats();

function adminHeaders(){const token=$("adminToken").value.trim();return token?{Authorization:'Bearer '+token}:{};}
$("copyReadLink").onclick=async()=>{
 if(window.ShuttleBrowser)return window.ShuttleBrowser.exportSession(state);
 if(!state.sessionId)return alert('请先创建会话');
 const link=new URL(location.href);link.search='?session='+encodeURIComponent(state.sessionId);link.hash='read='+encodeURIComponent(state.readToken);
 try{await navigator.clipboard.writeText(link.href);alert('只读显示链接已复制；持链接者可查看该会话。')}catch{prompt('复制只读显示链接',link.href)}
};
(async()=>{
 const id=new URLSearchParams(location.search).get('session'),read=new URLSearchParams(location.hash.slice(1)).get('read');
 if(!id||!read)return;history.replaceState(null,'',location.pathname);
 const response=await apiRequest('/api/sessions/'+encodeURIComponent(id),{headers:{Authorization:'Bearer '+read}});
 if(!response.ok)return setBadge('会话已失效或无权限',false);connect({...await response.json(),read_token:read});
})();
