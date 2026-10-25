"""Bounded, deterministic session review. No model, action recognition or medical inference."""
from __future__ import annotations
import math
import statistics
from datetime import datetime, timezone

GOALS = {
    'control': ('控球与节奏', [('节奏对拍', 6, '每组2分钟，保持同一节奏；人工记录连续成功拍数。'), ('定点落区', 6, '两组各3分钟，人工记录目标区域命中数。')]),
    'footwork': ('移动与回位', [('四点步法', 6, '三组各2分钟，教练观察每次回到准备位置。'), ('移动后控球', 6, '两组各3分钟，记录移动后仍能稳定完成的拍数。')]),
    'consistency': ('稳定与记录', [('固定机位复测', 6, '相同机位、比例与供球方式，采集三组短片。'), ('节奏重复', 6, '两组各3分钟，记录连续成功拍数与中断原因。')]),
}
SOURCE_LABELS={'simulated':'模拟坐标','device':'设备上报（未经独立验证）','unverified':'来源未验证','mixed':'混合来源'}


def collect_window(snapshot: dict, raw_points: list[dict]) -> dict:
    points=[]
    for point in raw_points[-300:]:
        values=[point.get(key) for key in ('x','y','timestamp')]
        if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in values):
            raise ValueError('Non-finite trajectory')
        x,y,timestamp=values
        if abs(x)>1e9 or abs(y)>1e9 or timestamp<0:
            raise ValueError('Trajectory outside supported range')
        if points and timestamp<=points[-1]['timestamp']:
            raise ValueError('Trajectory timestamps must increase')
        source=point.get('source','unverified')
        points.append({'x':x,'y':y,'timestamp':timestamp,'source':source if source in {'simulated','device','unverified'} else 'unverified'})
    scale=snapshot.get('px_per_meter')
    if scale is not None and (isinstance(scale,bool) or not isinstance(scale,(int,float)) or not math.isfinite(scale) or scale<=0):
        raise ValueError('Invalid calibration')
    distances=[math.hypot(b['x']-a['x'],b['y']-a['y']) for a,b in zip(points,points[1:])]
    speeds=[distance/(b['timestamp']-a['timestamp']) for distance,a,b in zip(distances,points,points[1:])]
    if any(not math.isfinite(speed) for speed in speeds):raise ValueError('Non-finite speed')
    values=[speed/scale*3.6 for speed in speeds] if scale else speeds
    if any(not math.isfinite(value) for value in values):raise ValueError('Speed outside supported range')
    sources={point['source'] for point in points}
    source=next(iter(sources)) if len(sources)==1 else 'mixed' if sources else 'unverified'
    for point in points:
        point['elapsed_s']=round(point['timestamp']-points[0]['timestamp'],4)
    return {
        'points':points,'source':source,'source_label':SOURCE_LABELS[source],
        'contains_simulated':any(point['source']=='simulated' for point in points),
        'metrics':{'point_count':len(points),'interval_count':len(values),
            'duration_s':round(points[-1]['timestamp']-points[0]['timestamp'],4) if points else 0,
            'path_px':round(sum(distances),2),'unit':'km/h' if scale else 'px/s',
            'mean':round(statistics.mean(values),2) if values else None,
            'peak':round(max(values),2) if values else None,
            'coefficient_of_variation':round(statistics.pstdev(values)/statistics.mean(values),4) if values and statistics.mean(values)>0 else None,
            'px_per_meter':scale},
    }


def assess_window(window: dict) -> tuple[list[str],list[str]]:
    m=window['metrics'];observations=[]
    limits=['二维画面坐标与人工比例不能证明真实三维球速、落点或击球动作。',
            '窗口最多300个已接受坐标；间隔不是击球次数，当前报告不含更早数据。',
            '来源由发送端声明，并非设备真实性认证。']
    if window['contains_simulated']:
        limits.insert(0,'含模拟数据：只用于验证交互与计算链路，不能评价运动能力。')
    elif window['source']=='mixed':limits.insert(0,'混合来源：窗口中的来源声明不一致，不能视为同一测量条件。')
    if not m['px_per_meter']:limits.insert(0,'未标定：速度只报告px/s，不能转换为km/h。')
    if m['interval_count']<3:
        observations.append('有效间隔不足3个；先采集连续坐标，再进行窗口复盘。')
    else:
        observations.append(f"当前窗口{m['point_count']}个点 / {m['duration_s']}秒，平均{m['mean']} {m['unit']}，峰值{m['peak']} {m['unit']}。")
        cv=m['coefficient_of_variation']
        if cv is None:observations.append('坐标未移动；零速度有效，但相对波动无法定义。')
        else:observations.append(f'窗口速度相对波动为{cv*100:.1f}%；它同时受到轨迹、机位和检测误差影响，不等于技术稳定性评分。')
    return observations,limits


def plan_training(window: dict, goal: str) -> list[dict]:
    title,blocks=GOALS[goal]
    plan=[{'id':'prepare','title':'准备与标定','minutes':3,'instruction':'固定机位；记录已知长度对应像素。没有比例时继续保留px/s。','reason':'先明确测量条件。'}]
    for index,(name,minutes,instruction) in enumerate(blocks):
        plan.append({'id':f'{goal}-{index}','title':name,'minutes':minutes,'instruction':instruction,'reason':f'来自你选择的目标「{title}」，不是自动识别动作后的处方。'})
    plan.append({'id':'review','title':'复盘与留档','minutes':3,'instruction':'保存相同条件下的窗口报告；另记命中率和连续拍数，交由教练结合视频判断。','reason':f"当前数据来源：{window['source_label']}；仍需人工观察。"})
    return plan


def build_report(snapshot: dict, points: list[dict], goal: str='consistency') -> dict:
    if goal not in GOALS:raise ValueError('Unsupported training goal')
    window=collect_window(snapshot,points)
    observations,limits=assess_window(window)
    plan=plan_training(window,goal)
    tools=[{'name':'读取会话窗口','result':f"{window['metrics']['point_count']}个点，最多300个"},
           {'name':'核对标定与来源','result':f"{window['source_label']} · {window['metrics']['unit']}"},
           {'name':'统计窗口','result':f"{window['metrics']['interval_count']}个时间间隔"},
           {'name':'编排训练任务','result':f"{len(plan)}项 / {sum(row['minutes'] for row in plan)}分钟"}]
    # Explicit projection: no capabilities, credentials, arbitrary user objects or server paths.
    return {'schema_version':1,'generated_at':datetime.now(timezone.utc).isoformat(),
        'session':{key:snapshot.get(key) for key in ('session_id','venue_id','court_id')},
        'goal':goal,'goal_label':GOALS[goal][0],'engine':'本地规则工具 Agent',
        **window,'observations':observations,'limitations':limits,'plan':plan,'tools':tools}
