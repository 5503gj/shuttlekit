const state = { sessionId: null, socket: null, history: [] };
const $ = (id) => document.getElementById(id);

function setBadge(text, online) { const badge = $("connectionBadge"); badge.textContent = text; badge.className = `badge ${online ? "badge-online" : "badge-offline"}`; }
function render(data) {
  $("currentSpeed").textContent = Number(data.current_speed_kmh || 0).toFixed(1);
  $("peakSpeed").textContent = Number(data.peak_speed_kmh || 0).toFixed(1);
  $("averageSpeed").textContent = Number(data.average_speed_kmh || 0).toFixed(1);
  $("sampleCount").textContent = data.sample_count || 0;
  $("qualityLabel").textContent = data.quality === "outlier" ? "已过滤异常点" : data.status === "tracking" ? "追踪中" : "等待数据";
  $("lastUpdate").textContent = `最后更新 ${new Date().toLocaleTimeString()}`;
  if (data.last_point && data.quality !== "outlier") { state.history.push(Number(data.last_point.speed_kmh || 0)); state.history = state.history.slice(-30); }
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
  closeSocket(); state.history = []; state.sessionId = session.session_id;
  const protocol = location.protocol === "https:" ? "wss" : "ws";
  state.socket = new WebSocket(`${protocol}://${location.host}/ws/sessions/${state.sessionId}`);
  state.socket.onopen = () => setBadge("实时已连接", true);
  state.socket.onclose = () => setBadge("连接已断开", false);
  state.socket.onerror = () => setBadge("连接异常", false);
  state.socket.onmessage = (event) => { const data = JSON.parse(event.data); if (!data.error) render(data); };
  $("sessionLabel").textContent = `${session.venue_id} / ${session.court_id} · ${session.session_id}`;
  $("resetBtn").disabled = false; render(session);
}
async function createSession() {
  const body = { venue_id: $("venueId").value.trim(), court_id: $("courtId").value.trim(), fps: Number($("fps").value), px_per_meter: Number($("pxPerMeter").value) };
  if (!body.venue_id || !body.court_id) return alert("请填写球馆 ID 和场地 ID");
  const response = await fetch("/api/sessions", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  if (!response.ok) return alert("创建会话失败，请检查参数"); connect(await response.json());
}
function sendPoint(x, y, timestamp) { if (!state.socket || state.socket.readyState !== WebSocket.OPEN) return alert("请先创建并连接实时会话"); state.socket.send(JSON.stringify({ type: "point", x, y, timestamp })); }
async function simulateShot(targetSpeed) {
  if (!state.sessionId) return alert("请先创建实时会话");
  const pxPerMeter = Number($("pxPerMeter").value) || 50, interval = 80, distance = targetSpeed / 3.6 * pxPerMeter * interval / 1000, start = performance.now() / 1000;
  for (let i = 0; i < 8; i++) { sendPoint(i * distance, 180 + Math.sin(i * .8) * 12, start + i * interval / 1000); await new Promise((resolve) => setTimeout(resolve, 45)); }
}
$("createBtn").addEventListener("click", createSession);
$("resetBtn").addEventListener("click", () => { if (state.socket?.readyState === WebSocket.OPEN) state.socket.send(JSON.stringify({ type: "reset" })); state.history = []; });
document.querySelectorAll(".shot-button").forEach((button) => button.addEventListener("click", () => simulateShot(Number(button.dataset.speed))));
window.addEventListener("resize", drawChart); drawChart();
