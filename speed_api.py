"""Local MVP with explicit capabilities, bounded uploads and shared broadcasts."""
from __future__ import annotations
import asyncio
import hmac
import json
import os
import secrets
import tempfile
from collections import defaultdict
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional,Literal
from fastapi import FastAPI,File,Form,Header,HTTPException,UploadFile,WebSocket,WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel,ConfigDict,Field,FiniteFloat
from starlette.concurrency import run_in_threadpool
from starlette.formparsers import MultiPartException
from shuttle_speed.realtime import SpeedSessionStore
from shuttle_speed.video_speed import VideoSpeedAnalyzer
from equipment_kb.recommender import EquipmentRecommender,UserProfile
from training_coach import build_report

PUBLIC_MODE=os.getenv("SHUTTLEKIT_PUBLIC")=="1" or os.getenv("HOST","127.0.0.1") not in {"127.0.0.1","localhost","::1"}
ADMIN_TOKEN=os.getenv("SHUTTLEKIT_ADMIN_TOKEN","")
ALLOWED_ORIGINS=set(filter(None,os.getenv("SHUTTLEKIT_ORIGINS","").split(',')))
MAX_VIDEO_BYTES=50*1024*1024
store=SpeedSessionStore()
video_analyzer=VideoSpeedAnalyzer()
equipment_recommender=EquipmentRecommender()
capabilities={}
subscribers=defaultdict(set)
mutation_locks=defaultdict(asyncio.Lock)
video_slots=asyncio.Semaphore(2)

@asynccontextmanager
async def lifespan(app):
    if PUBLIC_MODE and (len(ADMIN_TOKEN)<32 or not ALLOWED_ORIGINS):
        raise RuntimeError("Public mode requires SHUTTLEKIT_ADMIN_TOKEN (32+ chars) and SHUTTLEKIT_ORIGINS")
    yield

class UploadLimit:
    def __init__(self,app):self.app=app
    async def __call__(self,scope,receive,send):
        if scope['type']!='http' or scope.get('path')!='/api/video/analyze':
            return await self.app(scope,receive,send)
        count=0;exceeded=False
        async def bounded_receive():
            nonlocal count,exceeded
            message=await receive();count+=len(message.get('body',b''))
            if count>MAX_VIDEO_BYTES+65536:
                exceeded=True
                raise MultiPartException("Video body too large")
            return message
        async def bounded_send(message):
            if exceeded and message['type']=='http.response.start':message['status']=413
            await send(message)
        await self.app(scope,bounded_receive,bounded_send)

app=FastAPI(title='ShuttleKit Speed API',version='0.3.0',lifespan=lifespan)
app.add_middleware(UploadLimit)
app.add_middleware(CORSMiddleware,allow_origins=sorted(ALLOWED_ORIGINS),allow_methods=["GET","POST"],allow_headers=["Authorization","Content-Type"],allow_credentials=False)

class StrictModel(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
class SessionCreate(StrictModel):
    venue_id:str=Field(min_length=1,max_length=80)
    court_id:str=Field(min_length=1,max_length=80)
    fps:FiniteFloat=Field(default=60,gt=0,le=240)
    px_per_meter:Optional[FiniteFloat]=Field(default=None,gt=0,le=1000000)
class PointPayload(StrictModel):
    x:FiniteFloat=Field(ge=-1e9,le=1e9)
    y:FiniteFloat=Field(ge=-1e9,le=1e9)
    timestamp:Optional[FiniteFloat]=Field(default=None,ge=0)
    source:Literal['simulated','device','unverified']='unverified'
class EquipmentRecommendPayload(StrictModel):
    category:str=Field(default='racket',pattern='^(racket|shoe|shuttlecock)$')
    level:str=Field(default='中级',pattern='^(入门|初级|中级|高级|新手|进阶|专业|资深|初中级|中高级|业余|初学者|娱乐)$')
    budget:FiniteFloat=Field(default=800,ge=0,le=100000)
    play_style:str=Field(default='全面',pattern='^(全面|进攻|速度|防守|双打|单打|双打前场|双打后场|比赛|训练|娱乐|控制|均衡)$')
    gender:str=Field(default='不限',pattern='^(男|女|不限)$')
    top_k:int=Field(default=5,ge=1,le=10)

def require_admin(authorization,local_create=False):
    if local_create and not PUBLIC_MODE:return
    token=(authorization or '').removeprefix('Bearer ')
    if not ADMIN_TOKEN or not hmac.compare_digest(token,ADMIN_TOKEN):
        raise HTTPException(403,'Administrator credential required')

def _session_or_404(session_id):
    try:return store.get(session_id)
    except KeyError:raise HTTPException(404,'Session unavailable') from None

def authorize(session_id,token,write=False):
    credentials=capabilities.get(session_id,{})
    provided=(token or '').removeprefix('Bearer ')
    if not provided:raise HTTPException(403,'Session credential required')
    writer=hmac.compare_digest(provided,credentials.get('write',''))
    reader=hmac.compare_digest(provided,credentials.get('read',''))
    if not writer and (write or not reader):raise HTTPException(403,'Permission denied')
    return _session_or_404(session_id)

async def broadcast(session_id,state):
    for socket in list(subscribers.get(session_id,())):
        try:await asyncio.wait_for(socket.send_json(state),timeout=1)
        except Exception:subscribers[session_id].discard(socket)

@app.get('/api/health')
def health():return {'status':'ok','service':'shuttlekit-speed','mode':'public' if PUBLIC_MODE else 'local-demo'}

@app.post('/api/sessions')
def create_session(payload:SessionCreate,authorization:Optional[str]=Header(default=None)):
    require_admin(authorization,local_create=True)
    try:session=store.create(payload.venue_id,payload.court_id,payload.fps,payload.px_per_meter)
    except ValueError as exc:raise HTTPException(429,str(exc)) from exc
    for key in list(capabilities):
        if key not in store.sessions:capabilities.pop(key,None);mutation_locks.pop(key,None)
    capabilities[session.session_id]={'write':secrets.token_urlsafe(32),'read':secrets.token_urlsafe(32)}
    return {**session.snapshot(),'write_token':capabilities[session.session_id]['write'],'read_token':capabilities[session.session_id]['read']}

@app.get('/api/sessions/{session_id}')
def get_session(session_id:str,authorization:Optional[str]=Header(default=None)):
    return authorize(session_id,authorization).snapshot()

@app.get('/api/venues/{venue_id}/overview')
def venue_overview(venue_id:str,authorization:Optional[str]=Header(default=None)):
    require_admin(authorization);return {'venue_id':venue_id,'courts':store.overview(venue_id)}

@app.post('/api/sessions/{session_id}/points')
async def add_point(session_id:str,payload:PointPayload,authorization:Optional[str]=Header(default=None)):
    session=authorize(session_id,authorization,write=True)
    async with mutation_locks[session_id]:
        try:state=session.add_point(payload.x,payload.y,payload.timestamp,source=payload.source)
        except ValueError as exc:raise HTTPException(422,str(exc)) from exc
        await broadcast(session_id,state);return state

@app.get('/api/sessions/{session_id}/coach')
async def session_coach(session_id:str,goal:Literal['control','footwork','consistency']='consistency',authorization:Optional[str]=Header(default=None)):
    session=authorize(session_id,authorization)
    async with mutation_locks[session_id]:
        try:return build_report(session.snapshot(),session.points,goal)
        except ValueError as exc:raise HTTPException(422,str(exc)) from exc

@app.post('/api/sessions/{session_id}/reset')
async def reset_session(session_id:str,authorization:Optional[str]=Header(default=None)):
    session=authorize(session_id,authorization,write=True)
    async with mutation_locks[session_id]:
        state=session.reset();await broadcast(session_id,state);return state

def _equipment_item_view(item: dict) -> dict:
    """只返回前端需要的字段，同时保留来源，避免无来源推荐。"""
    return {
        "id": item.get("id"), "category": item.get("category"),
        "brand": item.get("brand"), "model": item.get("model"),
        "price_min": item.get("price_min"), "price_max": item.get("price_max"),
        "specs": item.get("specs") or {}, "play_styles": item.get("play_styles") or [],
        "levels": item.get("levels") or [], "rating": item.get("rating"),
        "review_summary": item.get("review_summary", ""),
        "source": item.get("source", "未标注来源"),
        "source_url": item.get("source_url", ""),
    }


@app.get("/api/equipment/stats")
def equipment_stats() -> dict:
    stats = equipment_recommender.get_stats()
    return {"stats": stats, "total": len(equipment_recommender.equipment),
            "data_policy": "品牌规格 + 公开评测人工整理；非实时爬取"}


@app.get("/api/equipment/catalog")
def equipment_catalog(category: Optional[str] = None) -> dict:
    allowed = {"racket", "shoe", "shuttlecock"}
    if category and category not in allowed:
        raise HTTPException(status_code=422, detail="category 必须是 racket、shoe 或 shuttlecock")
    items = equipment_recommender.equipment if not category else equipment_recommender.get_by_category(category)
    return {"category": category, "count": len(items), "items": [_equipment_item_view(item) for item in items]}


@app.post("/api/equipment/recommend")
def equipment_recommend(payload: EquipmentRecommendPayload) -> dict:
    profile = UserProfile(payload.category, payload.level, payload.budget,
                          payload.play_style, payload.gender)
    matches = equipment_recommender.recommend(profile, top_k=payload.top_k)
    profile_data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    return {
        "profile": profile_data,
        "count": len(matches),
        "results": [{"score": round(match.score, 1), "reasons": match.reasons,
                      "item": _equipment_item_view(match.item)} for match in matches],
    }



@app.post('/api/video/analyze')
async def analyze_video(file:UploadFile=File(...),px_per_meter:Optional[FiniteFloat]=Form(default=None,gt=0,le=1000000),authorization:Optional[str]=Header(default=None)):
    require_admin(authorization,local_create=True)
    suffix=Path(file.filename or '').suffix.lower()
    if suffix not in {'.mp4','.mov','.avi','.mkv','.webm'}:raise HTTPException(415,'Unsupported video format')
    try:await asyncio.wait_for(video_slots.acquire(),timeout=.05)
    except asyncio.TimeoutError:raise HTTPException(429,'Video workers busy') from None
    temp_path=None
    try:
        with tempfile.NamedTemporaryFile(delete=False,suffix=suffix) as temp:
            temp_path=temp.name;size=0
            while chunk:=await file.read(1024*1024):
                size+=len(chunk)
                if size>MAX_VIDEO_BYTES:raise HTTPException(413,'Video exceeds 50 MiB')
                temp.write(chunk)
        result=await run_in_threadpool(video_analyzer.analyze,temp_path,video_name=file.filename,px_per_meter=px_per_meter)
        return result.to_dict()
    except (FileNotFoundError,ValueError) as exc:raise HTTPException(422,str(exc)) from exc
    finally:
        await file.close()
        if temp_path:Path(temp_path).unlink(missing_ok=True)
        video_slots.release()

@app.websocket('/ws/sessions/{session_id}')
async def speed_socket(websocket:WebSocket,session_id:str):
    origin=websocket.headers.get('origin')
    expected=('https://' if websocket.url.scheme=='wss' else 'http://')+websocket.headers.get('host','')
    if origin and origin not in ALLOWED_ORIGINS and origin!=expected:
        await websocket.close(code=1008);return
    await websocket.accept()
    try:
        auth=await asyncio.wait_for(websocket.receive_json(),timeout=3)
        if not isinstance(auth,dict) or auth.get('type')!='auth':raise ValueError('Auth frame required')
        token=auth.get('token')
        if not isinstance(token,str):raise ValueError('Invalid token')
        session=authorize(session_id,token)
        if len(subscribers[session_id])>=16:raise ValueError('Subscriber capacity exceeded')
        subscribers[session_id].add(websocket)
        await websocket.send_json(session.snapshot())
        while True:
            raw=await websocket.receive_text()
            if len(raw)>4096:raise ValueError('Frame too large')
            event=json.loads(raw)
            if not isinstance(event,dict):raise ValueError('Invalid event')
            session=authorize(session_id,token,write=True)
            async with mutation_locks[session_id]:
                if event.get('type')=='reset':state=session.reset()
                elif event.get('type','point')=='point':
                    point=PointPayload.model_validate({k:v for k,v in event.items() if k!='type'})
                    state=session.add_point(point.x,point.y,point.timestamp,source=point.source)
                else:raise ValueError('Unknown event')
                await broadcast(session_id,state)
    except WebSocketDisconnect:pass
    except Exception:
        try:await websocket.close(code=1008,reason='Invalid request or permission')
        except Exception:pass
    finally:
        subscribers[session_id].discard(websocket)
        if not subscribers[session_id]:subscribers.pop(session_id,None)

WEB_DIR=Path(__file__).parent/'web'
app.mount('/',StaticFiles(directory=WEB_DIR,html=True),name='web')
if __name__=='__main__':
    import uvicorn
    uvicorn.run('speed_api:app',host=os.getenv('HOST','127.0.0.1'),port=int(os.getenv('PORT','7862')),ws_max_size=4096)
