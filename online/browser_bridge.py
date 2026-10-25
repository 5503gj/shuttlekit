"""In-page adapter for the same bounded session, coach, equipment and CV algorithms."""
import base64
import io
import json
import math
import secrets
from pathlib import Path
import cv2
import numpy as np
from PIL import Image
from shuttle_speed.realtime import SpeedSessionStore
from shuttle_speed.video_speed import VideoSpeedAnalyzer,VideoSpeedReport,CourtSizeEstimate
from shuttle_speed.speed_calc import SpeedCalculator,finite
from training_coach import build_report
from equipment_kb.recommender import EquipmentRecommender,UserProfile

store=SpeedSessionStore()
capabilities={}
equipment=EquipmentRecommender()
video_analyzer=VideoSpeedAnalyzer()
video=None

def authorize(sid,token,write=False):
    credentials=capabilities.get(sid,{})
    if token!=credentials.get('write') and (write or token!=credentials.get('read')):
        raise ValueError('无权访问此浏览器会话')
    if not token:raise ValueError('缺少会话凭据')
    return store.get(sid)

def checked_scale(value):
    if value is None:return None
    value=finite(value,'px_per_meter')
    if not 0<value<=1e6:raise ValueError('比例需在0至100万内')
    return value

def start_video(request):
    global video
    duration=finite(request['duration'],'duration')
    if not 0<duration<=60:raise ValueError('视频最多60秒')
    video={'name':str(request.get('name','browser-video'))[:120],'duration':duration,'scale':checked_scale(request.get('scale')),
        'frames':0,'points':[],'times':[],'previous_gray':None,'previous_point':None,'last_time':None}
    return {'ready':True}

def video_frame(request):
    if video is None:raise ValueError('请先选择视频')
    timestamp=finite(request['timestamp'],'timestamp')
    if timestamp<0 or timestamp>video['duration']+.01 or (video['last_time'] is not None and timestamp<=video['last_time']):raise ValueError('视频采样时间无效')
    image=Image.open(io.BytesIO(base64.b64decode(request['frame'],validate=True)))
    if image.width*image.height>1280*720:raise ValueError('采样帧超过720p')
    if video['frames']>=600:raise ValueError('最多600个采样帧')
    rgb=np.asarray(image.convert('RGB'));frame=cv2.cvtColor(rgb,cv2.COLOR_RGB2BGR)
    point=video_analyzer._detect_shuttle(frame,video['previous_gray'],video['previous_point'])
    video['previous_gray']=cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY);video['frames']+=1;video['last_time']=timestamp
    if point is not None:video['points'].append(point);video['times'].append(timestamp);video['previous_point']=point
    return {'frames':video['frames'],'point':point}

def finish_video():
    global video
    if video is None or not video['frames']:raise ValueError('视频没有可解码画面')
    data=video;video=None
    fps=data['frames']/data['duration'];scale=data['scale']
    result=SpeedCalculator(fps,scale).calculate(data['points'],timestamps=data['times'])
    points=data['points'];angle=math.degrees(math.atan2(points[-1][1]-points[0][1],points[-1][0]-points[0][0])) if len(points)>1 else None
    label,_=video_analyzer._classify_shot(result.max_speed_kmh,len(points)/data['frames'],None)
    warnings=['浏览器最多10Hz、600帧、720p采样；无法捕捉高速飞行的完整过程。','仅亮度与运动候选点，不是已验证的羽毛球识别；二维比例不等于真实三维测速。','时间戳来自实际解码位置；检测率以采样帧数为分母。']
    if scale is None:warnings.append('未标定，km/h为空；只输出px/s。')
    if result.rejected_samples:warnings.append(f'{result.rejected_samples}个间隔超过阈值，未作为零速度。')
    return VideoSpeedReport(data['name'],fps,data['frames'],data['duration'],len(points),len(points)/data['frames'],CourtSizeEstimate(px_per_meter=scale,source='manual-scale' if scale else 'unavailable'),result.max_speed_kmh,result.avg_speed_kmh,None,result.speed_curve[-120:],label,None,warnings,max(result.pixel_speed_curve) if result.pixel_speed_curve else None,angle,'2d_projected' if scale else 'uncalibrated').to_dict()

def api(request):
    path=request['path'];method=request.get('method','GET');body=request.get('body') or {};token=request.get('token','')
    if path=='/api/equipment/stats':return {'stats':equipment.get_stats(),'total':len(equipment.equipment)}
    if path=='/api/equipment/recommend':
        profile=UserProfile(body.get('category','racket'),body.get('level','中级'),body.get('budget',800),body.get('play_style','全面'),body.get('gender','不限'))
        matches=equipment.recommend(profile,top_k=min(10,max(1,int(body.get('top_k',6)))))
        return {'results':[{'item':row.item,'score':round(row.score,1),'reasons':row.reasons} for row in matches]}
    if path=='/api/sessions' and method=='POST':
        for key in ('venue_id','court_id'):
            if not isinstance(body.get(key),str) or not 0<len(body[key])<=80:raise ValueError('场馆和场地ID需1至80字')
        fps=finite(body.get('fps',60),'fps')
        if not 0<fps<=240:raise ValueError('FPS需在0至240内')
        value=store.create(body['venue_id'],body['court_id'],fps,checked_scale(body.get('px_per_meter')))
        for key in list(capabilities):
            if key not in store.sessions:capabilities.pop(key)
        caps={'write':secrets.token_hex(16),'read':secrets.token_hex(16)};capabilities[value.session_id]=caps
        return {**value.snapshot(),'write_token':caps['write'],'read_token':caps['read']}
    parts=path.strip('/').split('/')
    if len(parts)<3 or parts[:2]!=['api','sessions']:raise ValueError('接口不存在')
    sid=parts[2];operation=parts[3] if len(parts)>3 else ''
    value=authorize(sid,token,write=operation in {'points','reset'})
    if operation=='coach':return build_report(value.snapshot(),value.points,request.get('goal','consistency'))
    if operation=='reset':return value.reset()
    if operation=='points':
        x,y=finite(body.get('x'),'x'),finite(body.get('y'),'y')
        if abs(x)>1e9 or abs(y)>1e9:raise ValueError('坐标超限')
        return value.add_point(x,y,body.get('timestamp'),source=body.get('source','unverified'))
    if operation=='export':return build_report(value.snapshot(),value.points)
    if not operation:return value.snapshot()
    raise ValueError('接口不存在')

def dispatch(raw):
    request=json.loads(raw);action=request['action']
    if action=='api':
        try:result={'status':200,'body':api(request)}
        except (ValueError,KeyError,TypeError) as error:result={'status':422,'body':{'detail':str(error)}}
    elif action=='video_start':result=start_video(request)
    elif action=='video_frame':result=video_frame(request)
    elif action=='video_finish':result=finish_video()
    elif action=='video_clear':
        global video
        video=None;result={}
    else:raise ValueError('未知浏览器工具')
    return json.dumps(result,ensure_ascii=False,allow_nan=False)
