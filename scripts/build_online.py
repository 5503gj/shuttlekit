from pathlib import Path
import shutil,zipfile
from vendor_pyodide import vendor
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'dist';OUT.mkdir(exist_ok=True)
shutil.copytree(ROOT/'web',OUT,dirs_exist_ok=True);shutil.copytree(ROOT/'online',OUT,dirs_exist_ok=True)
source=(OUT/'index.html').read_text(encoding='utf8').replace('="/','="./')
source=source.replace('<script src="./app.js"></script><script src="./coach.js"></script>','<script type="module" src="online-loader.js"></script>')
source=source.replace('复制只读链接','导出当前轨迹').replace('<details class="access-details">','<details class="access-details" hidden>')
source=source.replace('真实接入：外部检测器 → 球心坐标与时间戳 → 人工比例 → 带凭据推送。当前未内置已验证的摄像头识别模型。','在线版：浏览器内计算，数据不上传，无需启动服务器。跨设备实时采集与同步由独立Python服务提供。')
source=source.replace('<button id="createBtn"','<p id="engineStatus" class="panel-note" role="status">首次加载浏览器引擎约28MB，随后使用缓存。</p><button id="retryEngine" class="button button-quiet" hidden>重试加载引擎</button><button id="createBtn"')
source=source.replace('<p class="integration-note">','<label class="trajectory-import">导入轨迹JSON<input id="importTrajectory" type="file" accept="application/json,.json"></label><p id="importStatus" class="panel-note" role="status"></p><p class="integration-note">')
source=source.replace('固定机位短视频，提取移动候选点。场地尺寸未测量，比例需人工输入；不等于已验证的羽毛球识别或三维测速。','浏览器采样视频画面并用原有OpenCV算法提取移动候选点；最多60秒、720p、10Hz。输入原视频像素比例，采样时同步缩放；不是专业高速或三维测速。')
source=source.replace('<div class="video-upload-row">','<p class="panel-note">浏览器能解码的MP4 / WebM / MOV；文件不上传，逐帧抽样耗时受设备影响。</p><div class="video-upload-row">')
source=source.replace('<button id="analyzeVideoBtn"','<button id="cancelVideo" class="button button-quiet" hidden>取消视频分析</button><button id="analyzeVideoBtn"')
source=source.replace('SHUTTLEKIT / 测量有边界，训练有方向。','SHUTTLEKIT / 浏览器在线版 · 数据不上传')
(OUT/'index.html').write_text(source,encoding='utf8')
with zipfile.ZipFile(OUT/'python-source.zip','w',zipfile.ZIP_DEFLATED) as zipped:
    for name in ('shuttle_speed/__init__.py','shuttle_speed/realtime.py','shuttle_speed/speed_calc.py','shuttle_speed/track.py','shuttle_speed/video_speed.py','training_coach.py','equipment_kb/__init__.py','equipment_kb/recommender.py','equipment_kb/equipment.json'):
        zipped.write(ROOT/name,name)
    zipped.write(ROOT/'online/browser_bridge.py','browser_bridge.py')
vendor(OUT/'runtime',ROOT/'.runtime-cache');(OUT/'.nojekyll').touch()
