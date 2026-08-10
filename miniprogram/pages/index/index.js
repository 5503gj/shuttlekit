const app = getApp();
Page({
  data: { venueId: 'shanghai-center', courtId: 'court-01', connected: false, statusText: '尚未连接', currentSpeed: '0.0', peakSpeed: '0.0', sampleCount: 0 },
  socketTask: null,
  sessionId: '',
  onVenueInput(e) { this.setData({ venueId: e.detail.value }); },
  onCourtInput(e) { this.setData({ courtId: e.detail.value }); },
  connectSession() {
    wx.request({ url: `${app.globalData.apiBaseUrl}/api/sessions`, method: 'POST', data: { venue_id: this.data.venueId, court_id: this.data.courtId, fps: 60, px_per_meter: 50 }, success: (res) => { this.sessionId = res.data.session_id; this.openSocket(); }, fail: () => this.setData({ statusText: '接口连接失败，请确认 Python 服务已启动' }) });
  },
  openSocket() {
    if (this.socketTask) this.socketTask.close();
    this.socketTask = wx.connectSocket({ url: `${app.globalData.wsBaseUrl}/ws/sessions/${this.sessionId}` });
    this.socketTask.onOpen(() => this.setData({ connected: true, statusText: `已连接 ${this.data.courtId}` }));
    this.socketTask.onClose(() => this.setData({ connected: false, statusText: '连接已断开' }));
    this.socketTask.onMessage((event) => { const data = JSON.parse(event.data); if (!data.error) this.renderState(data); });
  },
  renderState(data) { this.setData({ currentSpeed: Number(data.current_speed_kmh || 0).toFixed(1), peakSpeed: Number(data.peak_speed_kmh || 0).toFixed(1), sampleCount: data.sample_count || 0, statusText: data.status === 'tracking' ? '实时追踪中' : '等待击球' }); },
  simulateShot(e) {
    if (!this.socketTask || !this.data.connected) return wx.showToast({ title: '请先连接场地', icon: 'none' });
    const speed = Number(e.currentTarget.dataset.speed), pxPerMeter = 50, interval = 80, distance = speed / 3.6 * pxPerMeter * interval / 1000, start = Date.now() / 1000;
    for (let i = 0; i < 8; i += 1) setTimeout(() => this.socketTask.send({ data: JSON.stringify({ type: 'point', x: i * distance, y: 180 + Math.sin(i * 0.8) * 12, timestamp: start + i * interval / 1000 }) }), i * 45);
  },
  resetSession() { if (this.socketTask && this.data.connected) this.socketTask.send({ data: JSON.stringify({ type: 'reset' }) }); },
  onUnload() { if (this.socketTask) this.socketTask.close(); },
});
