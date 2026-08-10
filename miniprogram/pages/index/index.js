const app = getApp();
Page({
  data: { venueId: 'shanghai-center', courtId: 'court-01', connected: false, statusText: '尚未连接', currentSpeed: '0.0', peakSpeed: '0.0', sampleCount: 0, equipmentCategories: [{ label: '球拍', value: 'racket' }, { label: '球鞋', value: 'shoe' }, { label: '羽毛球', value: 'shuttlecock' }], equipmentCategoryIndex: 0, equipmentLevels: ['入门', '中级', '高级'], equipmentLevelIndex: 1, equipmentStyles: ['全面', '进攻', '速度', '双打后场', '双打前场', '比赛', '训练'], equipmentStyleIndex: 0, equipmentBudget: '1000', equipmentResults: [], equipmentLoading: false },
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
  onEquipmentCategoryChange(e) { this.setData({ equipmentCategoryIndex: Number(e.detail.value) }); },
  onEquipmentLevelChange(e) { this.setData({ equipmentLevelIndex: Number(e.detail.value) }); },
  onEquipmentStyleChange(e) { this.setData({ equipmentStyleIndex: Number(e.detail.value) }); },
  onEquipmentBudgetInput(e) { this.setData({ equipmentBudget: e.detail.value }); },
  recommendEquipment() {
    this.setData({ equipmentLoading: true });
    const category = this.data.equipmentCategories[this.data.equipmentCategoryIndex].value;
    wx.request({ url: `${app.globalData.apiBaseUrl}/api/equipment/recommend`, method: 'POST', data: { category, level: this.data.equipmentLevels[this.data.equipmentLevelIndex], budget: Number(this.data.equipmentBudget) || 0, play_style: this.data.equipmentStyles[this.data.equipmentStyleIndex], gender: '不限', top_k: 5 }, success: (res) => { const results = (res.data.results || []).map((match) => { const item = match.item; const priceText = item.price_min != null && item.price_max != null ? `${item.price_min}-${item.price_max}元` : '价格以实际渠道为准'; return { ...match, reasonsText: (match.reasons || []).join(' · ') || '综合匹配', item: { ...item, priceText } }; }); this.setData({ equipmentResults: results }); }, fail: () => wx.showToast({ title: '装备推荐接口失败', icon: 'none' }), complete: () => this.setData({ equipmentLoading: false }) });
  },
  onUnload() { if (this.socketTask) this.socketTask.close(); },
});
