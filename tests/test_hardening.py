import json
import socket
import sys
import threading
import time
from types import SimpleNamespace

import cv2
import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient
from websockets.sync.client import connect
import uvicorn

import speed_api as api
from court_lighting.brightness import BrightnessAnalyzer
from equipment_kb.recommender import EquipmentRecommender, UserProfile
from match_stats.recorder import MatchRecorder
from shuttle_speed.realtime import RealtimeSpeedSession, SpeedSessionStore
from shuttle_speed.speed_calc import SpeedCalculator
from shuttle_speed.track import ShuttleTracker
from shuttle_speed.video_speed import VideoSpeedAnalyzer


def test_photos_cannot_prove_lighting_compliance():
    for gray in [0,80,200,255]:
        conclusion,_=BrightnessAnalyzer()._evaluate(gray,1,0)
        assert '未测量' in conclusion
        assert '达标' not in conclusion


def test_arbitrary_line_does_not_calibrate_a_court():
    frame=np.zeros((200,500,3),np.uint8);cv2.line(frame,(0,100),(400,100),(255,255,255),2)
    court=VideoSpeedAnalyzer()._estimate_court(frame)
    assert court.px_per_meter is None and court.length_m is None and court.confidence is None


def test_missing_frames_use_elapsed_time(tmp_path):
    path=tmp_path/'points.csv';path.write_text('frame,x,y\n0,0,0\n30,50,0\n')
    report=ShuttleTracker(fps=30,method='manual',px_per_meter=50).track_from_csv(str(path))
    assert report.speed_report.max_speed_kmh==pytest.approx(3.6)
    assert report.total_frames==31
    assert report.detection_rate==pytest.approx(2/31)
    direct=SpeedCalculator(30,50).calculate([(0,0),(50,0)],timestamps=[0,1])
    assert direct.max_speed_kmh==pytest.approx(3.6)


def test_high_valid_speed_and_invalid_samples_are_distinct():
    good=SpeedCalculator(30,50).calculate([(0,0),(150,0)])
    assert good.max_speed_kmh==pytest.approx(324)
    bad=SpeedCalculator(30,50).calculate([(0,0),(1000000,0)])
    assert bad.max_speed_kmh is None and bad.status=='no_valid_samples'
    unscaled=SpeedCalculator(30).calculate([(0,0),(10,0)])
    assert unscaled.max_speed_kmh is None and unscaled.pixel_speed_curve==[300]


@pytest.mark.parametrize('kwargs',[{'fps':0},{'fps':float('nan')},{'px_per_meter':float('inf')},{'px_per_meter':-2}])
def test_calculator_invalid_inputs(kwargs):
    with pytest.raises(ValueError):SpeedCalculator(**kwargs)


def test_realtime_rejection_does_not_move_baseline_and_history_is_bounded():
    s=RealtimeSpeedSession('v','c',px_per_meter=50);s.add_point(0,0,0)
    with pytest.raises(ValueError):s.add_point(float('nan'),0,1)
    out=s.add_point(10000,0,.1)
    assert out['quality']=='outlier' and out['peak_speed_kmh'] is None
    result=s.add_point(10,0,.2)
    assert result['current_speed_kmh']==3.6
    for i in range(1,401):s.add_point(10+i,0,.2+i)
    assert len(s.points)<=300 and len(s.speed_history)<=300
    store=SpeedSessionStore();store.max_sessions=1;store.create('v','c')
    with pytest.raises(ValueError):store.create('v','another')


def test_tracknet_is_explicitly_unavailable():
    with pytest.raises(NotImplementedError):ShuttleTracker(method='tracknet').track_from_video('unused')


def test_yolo_ignores_small_wrong_category(tmp_path):
    path=tmp_path/'clip.avi';w=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'MJPG'),30,(64,64))
    for _ in range(3):w.write(np.zeros((64,64,3),np.uint8))
    w.release()
    wrong=SimpleNamespace(cls=[0],conf=[.99],xyxy=[np.array([1,1,2,2])])
    correct=SimpleNamespace(cls=[32],conf=[.9],xyxy=[np.array([10,10,20,20])])
    tracker=ShuttleTracker(px_per_meter=50);tracker._model=lambda *a,**k:[SimpleNamespace(boxes=[wrong,correct])]
    result=tracker._track_with_yolo(str(path),None)
    assert result.trajectory==[(15,15)]*3


def test_budget_and_enums_are_not_silently_relaxed():
    rec=EquipmentRecommender()
    assert rec.recommend(UserProfile(budget=0))==[]
    for profile in [UserProfile(category='oops'),UserProfile(budget=float('nan')),UserProfile(level='oops')]:
        with pytest.raises(ValueError):rec.recommend(profile)
    assert all(m.item['price_min']<=400 for m in rec.recommend(UserProfile(budget=400)))


def test_provider_errors_and_foreign_ids_fall_back(monkeypatch):
    from equipment_kb import ai_advisor
    def broken(**kwargs):raise RuntimeError('provider unavailable')
    fake=SimpleNamespace(OpenAI=lambda **kw:SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=broken))))
    monkeypatch.setitem(sys.modules,'openai',fake);monkeypatch.setenv('OPENAI_API_KEY','synthetic-placeholder')
    assert '规则引擎' in ai_advisor.advise(UserProfile())
    def foreign(**kwargs):
        message=SimpleNamespace(content=json.dumps({'recommendations':[{'id':'foreign','reason':'fake'}]}))
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])
    fake.OpenAI=lambda **kw:SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=foreign)))
    assert ai_advisor.recommend_with_llm(UserProfile()) is None


@pytest.mark.parametrize('values',[('X','A','杀球',2),('A','X','杀球',2),('A','B','假动作',2),('A','B','杀球',-1),('A','B','杀球',float('nan'))])
def test_bad_match_points_cannot_change_score(values):
    recorder=MatchRecorder()
    with pytest.raises(ValueError):recorder.add_point(*values)
    assert recorder.data.total_rallies()==0


def test_rest_capabilities_and_public_fail_closed(monkeypatch):
    with TestClient(api.app) as client:
        response=client.post('/api/sessions',json={'venue_id':'v','court_id':'c','px_per_meter':50}).json()
        sid=response['session_id'];reader={'Authorization':'Bearer '+response['read_token']};writer={'Authorization':'Bearer '+response['write_token']}
        assert client.get('/api/sessions/'+sid).status_code==403
        assert client.get('/api/sessions/'+sid,headers=reader).status_code==200
        assert client.post('/api/sessions/'+sid+'/reset',headers=reader).status_code==403
        assert client.post('/api/sessions/'+sid+'/reset',headers=writer).status_code==200
        other=client.post('/api/sessions',json={'venue_id':'other','court_id':'c'}).json()
        assert client.get('/api/sessions/'+other['session_id'],headers=reader).status_code==403
        assert client.get('/api/venues/v/overview').status_code==403
        monkeypatch.setattr(api,'PUBLIC_MODE',True)
        assert client.post('/api/sessions',json={'venue_id':'v','court_id':'c'}).status_code==403
    monkeypatch.setattr(api,'ADMIN_TOKEN','');monkeypatch.setattr(api,'ALLOWED_ORIGINS',set())
    with pytest.raises(RuntimeError),TestClient(api.app):pass


def test_video_upload_limit_and_background_worker(monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    started,release=threading.Event(),threading.Event()
    def analyze(*args,**kwargs):
        started.set();assert release.wait(3);return SimpleNamespace(to_dict=lambda:{'test':'ok'})
    monkeypatch.setattr(api.video_analyzer,'analyze',analyze)
    with TestClient(api.app) as client,ThreadPoolExecutor(2) as pool:
        pending=pool.submit(client.post,'/api/video/analyze',files={'file':('x.mp4',b'bounded')})
        try:
            assert started.wait(2)
            health=pool.submit(client.get,'/api/health')
            assert health.result(timeout=1).status_code==200
        finally:release.set()
        assert pending.result(timeout=3).status_code==200
        monkeypatch.setattr(api,'MAX_VIDEO_BYTES',32)
        assert client.post('/api/video/analyze',files={'file':('x.mp4',b'x'*64)}).status_code==413


def test_real_network_three_clients_receive_ws_and_http_changes():
    sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    server=uvicorn.Server(uvicorn.Config(api.app,log_level='warning',ws_max_size=4096))
    thread=threading.Thread(target=server.run,kwargs={'sockets':[sock]},daemon=True);thread.start()
    try:
        deadline=time.monotonic()+5
        while not server.started:
            assert time.monotonic()<deadline;time.sleep(.01)
        base=f'http://127.0.0.1:{port}';ws=f'ws://127.0.0.1:{port}'
        with httpx.Client(base_url=base,timeout=3) as client:
            session=client.post('/api/sessions',json={'venue_id':'v','court_id':'real','px_per_meter':50}).json();sid=session['session_id']
            with connect(ws+'/ws/sessions/'+sid,origin=base) as writer,connect(ws+'/ws/sessions/'+sid,origin=base) as display1,connect(ws+'/ws/sessions/'+sid,origin=base) as display2:
                for peer,token in [(writer,session['write_token']),(display1,session['read_token']),(display2,session['read_token'])]:
                    peer.send(json.dumps({'type':'auth','token':token}));json.loads(peer.recv(timeout=2))
                for x,t in [(0,0),(50,1/60)]:
                    writer.send(json.dumps({'type':'point','x':x,'y':0,'timestamp':t}))
                    values=[json.loads(peer.recv(timeout=2)) for peer in [writer,display1,display2]]
                    assert len({v['current_speed_kmh'] for v in values})==1
                assert values[2]['current_speed_kmh']==216
                assert client.post('/api/sessions/'+sid+'/reset',headers={'Authorization':'Bearer '+session['write_token']}).status_code==200
                assert all(json.loads(peer.recv(timeout=2))['quality']=='reset' for peer in [writer,display1,display2])
    finally:
        server.should_exit=True;thread.join(timeout=5);sock.close()
