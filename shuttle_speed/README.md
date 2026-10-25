# 轨迹与速度

SpeedCalculator(fps=30, px_per_meter=None).calculate(positions, frame_indices=...)或timestamps=...
显式保留漏检帧间隔。未标定输出pixel_speed_curve，km/h为空；提供有效比例才输出2D投影估计。
空轨迹/无有效样本不冒充0km/h；实际静止轨迹在有效标定后可为0。默认异常上限600km/h可配置，不再删除所有300km/h以上结果。

ShuttleTracker(method="manual",fps=30,px_per_meter=50).track_from_csv(path)读取frame,x,y。
YOLO需显式本地model_path、类别与置信阈值；不会自动下载。TrackNet明确未实现。
VideoSpeedAnalyzer().analyze(path,px_per_meter=None)不推断球场真实尺寸和物理俯角。
完整接口、权限、资源限制及企业部署差距见../docs/HARDENING.md。
