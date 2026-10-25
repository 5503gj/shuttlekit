import json
import math
import pytest
from fastapi.testclient import TestClient
import speed_api as api
from shuttle_speed.realtime import RealtimeSpeedSession
from training_coach import build_report


def session(scale=None, source='unverified'):
    value=RealtimeSpeedSession('venue','court',px_per_meter=scale)
    for i in range(5):value.add_point(i*10,0,i,source=source)
    return value


def test_unscaled_window_reports_pixels_and_traceable_inputs():
    value=session();snapshot=value.snapshot();snapshot['write_token']='sensitive-placeholder'
    value.points[0]['arbitrary']='must-not-export'
    report=build_report(snapshot,value.points)
    assert report['metrics']=={'point_count':5,'interval_count':4,'duration_s':4,'path_px':40,'unit':'px/s','mean':10,'peak':10,'coefficient_of_variation':0,'px_per_meter':None}
    assert len(report['tools'])==4 and sum(row['minutes'] for row in report['plan'])==18
    assert '未标定' in ' '.join(report['limitations'])
    assert 'sensitive-placeholder' not in json.dumps(report) and 'must-not-export' not in json.dumps(report)


def test_scaled_simulation_never_claims_measured_ability():
    value=session(50,'simulated');report=build_report(value.snapshot(),value.points,'control')
    assert report['metrics']['mean']==.72 and report['metrics']['unit']=='km/h'
    assert report['source']=='simulated' and '不能评价运动能力' in report['limitations'][0]
    assert '控球' in report['goal_label']
    assert all('目标' in row['reason'] for row in report['plan'][1:3])
    value.add_point(50,0,5,source='device')
    assert value.snapshot()['data_source']=='mixed'
    assert build_report(value.snapshot(),value.points)['source']=='mixed'
    value.reset();assert value.snapshot()['data_source']=='unverified'


def test_empty_and_stationary_are_not_fabricated_stats():
    value=RealtimeSpeedSession('v','c')
    empty=build_report(value.snapshot(),[])
    assert empty['metrics']['mean'] is None and empty['metrics']['peak'] is None
    value.add_point(0,0,0);value.add_point(0,0,1)
    still=build_report(value.snapshot(),value.points)
    assert still['metrics']['mean']==0 and still['metrics']['coefficient_of_variation'] is None


@pytest.mark.parametrize('points',[[{'x':math.nan,'y':0,'timestamp':0}],[{'x':0,'y':0,'timestamp':1},{'x':0,'y':0,'timestamp':1}],[{'x':1e10,'y':0,'timestamp':0}]])
def test_invalid_trajectory_is_rejected(points):
    with pytest.raises(ValueError):build_report({},points)


def test_bounded_window_and_outlier_source_cannot_pollute_report():
    value=session(50,'device')
    out=value.add_point(1000000,0,5,source='simulated')
    assert out['quality']=='outlier' and out['data_source']=='device'
    for i in range(5,405):value.add_point(i*10,0,i,source='device')
    report=build_report(value.snapshot(),value.points)
    assert len(report['points'])==300 and report['metrics']['interval_count']==299
    assert report['metrics']['duration_s']==299
    assert report['source']=='device' and report['contains_simulated'] is False
    with pytest.raises(ValueError):build_report({},[],'invented-goal')


def test_small_calibration_is_not_rounded_to_zero_in_reports():
    value=RealtimeSpeedSession('v','c',px_per_meter=.00001)
    value.add_point(0,0,0);value.add_point(.00001,0,1)
    report=build_report(value.snapshot(),value.points)
    assert report['metrics']['px_per_meter']==.00001
    assert report['metrics']['mean']==3.6


def test_coach_requires_same_session_capability_and_is_read_only():
    with TestClient(api.app) as client:
        created=client.post('/api/sessions',json={'venue_id':'v','court_id':'c'}).json()
        sid=created['session_id'];url=f'/api/sessions/{sid}/coach'
        read={'Authorization':'Bearer '+created['read_token']};write={'Authorization':'Bearer '+created['write_token']}
        assert client.get(url).status_code==403
        assert client.post(f'/api/sessions/{sid}/points',json={'x':0,'y':0,'timestamp':0,'source':'simulated'},headers=write).status_code==200
        assert client.post(f'/api/sessions/{sid}/points',json={'x':10,'y':0,'timestamp':1,'source':'simulated'},headers=write).status_code==200
        before=client.get(f'/api/sessions/{sid}',headers=read).json()
        report=client.get(url,headers=read).json()
        assert report['metrics']['unit']=='px/s' and report['source']=='simulated'
        assert before==client.get(f'/api/sessions/{sid}',headers=read).json()
        assert created['read_token'] not in json.dumps(report)
        assert created['write_token'] not in json.dumps(report)
        other=client.post('/api/sessions',json={'venue_id':'other','court_id':'c'}).json()
        assert client.get(f"/api/sessions/{other['session_id']}/coach",headers=read).status_code==403
        assert client.get(url+'?goal=invented',headers=read).status_code==422
        assert client.post(f'/api/sessions/{sid}/points',json={'x':1,'y':0,'timestamp':2,'source':'fabricated'},headers=write).status_code==422
