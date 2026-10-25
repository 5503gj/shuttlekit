/* Session tools stay read-only. Report inputs are frozen until the next explicit run. */
(() => {
  'use strict';
  const byId=id=>document.getElementById(id);
  const svgNS='http://www.w3.org/2000/svg';
  const labels={simulated:'模拟坐标 · 非实测',device:'设备声明 · 未验证',mixed:'混合来源 · 含不同声明',unverified:'来源未验证'};
  let points=[],sessionId=null,report=null,controller=null,generation=0,frame=null,playing=false,completed=new Set();
  const text=(tag,value,cls)=>{const node=document.createElement(tag);node.textContent=value;if(cls)node.className=cls;return node;};
  const signature=p=>p?`${p.x}/${p.y}/${p.timestamp}`:'';
  function stop(){playing=false;cancelAnimationFrame(frame);byId('replayBtn').textContent='▶ 回放';byId('replayBtn').setAttribute('aria-label','播放轨迹');}
  function cancel(){generation++;if(controller)controller.abort();controller=null;byId('coachRun').disabled=false;byId('coachCancel').hidden=true;}
  function clearReport(){cancel();report=null;completed.clear();byId('coachResult').hidden=true;byId('coachTools').replaceChildren(text('li','读取窗口 → 核对来源 → 统计 → 编排任务','tool-empty'));byId('coachStatus').textContent='会话已切换或清空，请重新复盘。';}
  function project(){
    if(!points.length)return[];
    const xs=points.map(p=>p.x),ys=points.map(p=>p.y);
    const minX=Math.min(...xs),minY=Math.min(...ys),spanX=Math.max(...xs)-minX,spanY=Math.max(...ys)-minY;
    const scale=Math.min(700/Math.max(spanX,1),220/Math.max(spanY,1));
    const offsetX=(860-spanX*scale)/2,offsetY=(400-spanY*scale)/2;
    return points.map(p=>({x:offsetX+(p.x-minX)*scale,y:offsetY+(p.y-minY)*scale}));
  }
  function draw(){
    const positions=project(),max=Math.max(0,points.length-1);byId('replayRange').max=String(max);byId('replayRange').disabled=points.length<2;byId('replayBtn').disabled=points.length<2;
    const index=Math.min(Number(byId('replayRange').value)||0,max),visible=positions.slice(0,index+1);
    byId('trajectoryPath').setAttribute('d',visible.map((p,i)=>`${i?'L':'M'}${p.x.toFixed(2)},${p.y.toFixed(2)}`).join(' '));
    const dots=visible.map(p=>{const circle=document.createElementNS(svgNS,'circle');circle.setAttribute('cx',p.x);circle.setAttribute('cy',p.y);circle.setAttribute('r',3);circle.setAttribute('class','trajectory-dot');return circle;});byId('trajectoryDots').replaceChildren(...dots);
    const cursor=byId('trajectoryCursor');cursor.hidden=!visible.length;cursor.style.display=visible.length?'':'none';
    if(visible.length){cursor.setAttribute('cx',visible.at(-1).x);cursor.setAttribute('cy',visible.at(-1).y);}
    byId('trajectoryEmpty').style.display=positions.length?'none':'';
    byId('replayTime').textContent=points.length?`${index+1} / ${points.length} · ${(points[index].timestamp-points[0].timestamp).toFixed(2)}s`:'0 / 0';
  }
  function replacePoints(next){stop();points=next.slice(-300);byId('replayRange').max=String(Math.max(0,points.length-1));byId('replayRange').value=String(Math.max(0,points.length-1));draw();}
  window.addEventListener('shuttle-state',event=>{
    const data=event.detail;
    if(sessionId!==data.session_id||data.quality==='reset'){sessionId=data.session_id;replacePoints([]);clearReport();}
    byId('sourceLabel').textContent=labels[data.data_source]||labels.unverified;
    if(data.last_point&&data.quality!=='outlier'&&signature(points.at(-1))!==signature(data.last_point))replacePoints([...points,data.last_point]);
    if(report&&signature(report.points.at(-1))!==signature(data.last_point))byId('coachStatus').textContent='采集窗口已更新；下方保留上次复盘快照，可重新运行。';
  });
  if(state.snapshot)window.dispatchEvent(new CustomEvent('shuttle-state',{detail:state.snapshot}));
  byId('replayRange').addEventListener('input',()=>{stop();draw();});
  byId('replayBtn').onclick=()=>{
    if(playing){stop();return;}
    if(points.length<2)return;
    playing=true;byId('replayBtn').textContent='Ⅱ 暂停';byId('replayBtn').setAttribute('aria-label','暂停轨迹');
    const start=performance.now(),duration=Math.max(800,Math.min(12000,(points.at(-1).timestamp-points[0].timestamp)*1000));
    byId('replayRange').value='0';draw();
    const tick=now=>{if(!playing)return;const ratio=Math.min(1,(now-start)/duration),elapsed=ratio*(points.at(-1).timestamp-points[0].timestamp);let index=0;while(index+1<points.length&&points[index+1].timestamp-points[0].timestamp<=elapsed)index++;byId('replayRange').value=String(index);draw();if(ratio===1)stop();else frame=requestAnimationFrame(tick);};frame=requestAnimationFrame(tick);
  };
  function displayReport(data){
    report=data;completed.clear();replacePoints(data.points);byId('sourceLabel').textContent=labels[data.source]||labels.unverified;
    byId('coachTools').replaceChildren(...data.tools.map(tool=>{const li=document.createElement('li');const detail=document.createElement('div');detail.append(text('strong',tool.name),text('small',tool.result));li.append(text('span','✓','tool-check'),detail);return li;}));
    byId('coachObservations').replaceChildren(...data.observations.map(value=>text('p',value)));
    byId('planDuration').textContent=`${data.plan.reduce((sum,row)=>sum+row.minutes,0)} 分钟`;
    byId('coachPlan').replaceChildren(...data.plan.map(row=>{
      const label=document.createElement('label');label.className='training-task';const check=document.createElement('input');check.type='checkbox';check.setAttribute('aria-label',`完成${row.title}`);
      const detail=document.createElement('div');detail.append(text('strong',`${row.title} · ${row.minutes}分钟`),text('small',row.instruction),text('small',row.reason,'task-reason'));
      check.onchange=()=>{check.checked?completed.add(row.id):completed.delete(row.id);byId('planProgress').textContent=`${completed.size} / ${data.plan.length} 已完成 · 仅本页记录`;};label.append(check,detail);return label;
    }));
    byId('planProgress').textContent=`0 / ${data.plan.length} 已完成 · 仅本页记录`;
    byId('coachLimits').replaceChildren(...data.limitations.map(value=>text('li',value)));byId('coachResult').hidden=false;
    const same=signature(data.points.at(-1))===signature(state.snapshot?.last_point);
    byId('coachStatus').textContent=same?`已生成 ${new Date(data.generated_at).toLocaleTimeString()} 的窗口快照；采集数据未更改。`:'复盘已完成；采集窗口已更新，请按需重新运行。';
  }
  byId('coachRun').onclick=async()=>{
    if(!state.sessionId){byId('coachStatus').textContent='先创建会话；也可用模拟按钮体验。';return;}
    cancel();const version=++generation;controller=new AbortController();const requestedSession=state.sessionId;
    byId('coachRun').disabled=true;byId('coachCancel').hidden=false;byId('coachStatus').textContent='正在读取会话窗口并核对数据…';
    try{
      const response=await fetch(`/api/sessions/${encodeURIComponent(requestedSession)}/coach?goal=${encodeURIComponent(byId('coachGoal').value)}`,{headers:{Authorization:'Bearer '+state.token},signal:controller.signal});
      if(!response.ok)throw new Error(response.status===403?'当前凭据无法读取此会话。':'会话不可用或参数无效，请重建后再试。');
      const data=await response.json();if(version!==generation||requestedSession!==state.sessionId)return;displayReport(data);
    }catch(error){if(version===generation)byId('coachStatus').textContent=error.name==='AbortError'?'复盘已取消，采集未更改。':error.message;}
    finally{if(version===generation){controller=null;byId('coachRun').disabled=false;byId('coachCancel').hidden=true;}}
  };
  byId('coachCancel').onclick=()=>{cancel();byId('coachStatus').textContent='复盘已取消，采集未更改。';};
  function download(kind){
    if(!report)return;
    const exported={...report,completed_task_ids:[...completed]};
    const md=`# ShuttleKit 训练复盘\n\n${report.generated_at}\n\n${report.engine} · ${report.source_label}\n\n目标：${report.goal_label}\n\n## 窗口观察\n\n${report.observations.join('\n\n')}\n\n## 练习清单\n\n${report.plan.map(row=>`- [${completed.has(row.id)?'x':' '}] ${row.title} / ${row.minutes}分钟：${row.instruction}\n  依据：${row.reason}`).join('\n')}\n\n## 解释边界\n\n${report.limitations.map(value=>'- '+value).join('\n')}\n`;
    const blob=new Blob([kind==='json'?JSON.stringify(exported,null,2):md],{type:kind==='json'?'application/json;charset=utf-8':'text/markdown;charset=utf-8'}),url=URL.createObjectURL(blob),link=document.createElement('a');link.download=`shuttlekit-review.${kind==='json'?'json':'md'}`;link.href=url;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
  byId('exportJson').onclick=()=>download('json');byId('exportMarkdown').onclick=()=>download('markdown');
  const tabs=[...document.querySelectorAll('[role=tab][data-tab]')];
  function activate(button){tabs.forEach(tab=>{const selected=tab===button;tab.setAttribute('aria-selected',String(selected));tab.tabIndex=selected?0:-1;byId('panel-'+tab.dataset.tab).hidden=!selected;});}
  tabs.forEach((tab,index)=>{tab.onclick=()=>activate(tab);tab.onkeydown=event=>{let next;if(event.key==='ArrowRight')next=(index+1)%tabs.length;if(event.key==='ArrowLeft')next=(index+tabs.length-1)%tabs.length;if(event.key==='Home')next=0;if(event.key==='End')next=tabs.length-1;if(next!==undefined){event.preventDefault();activate(tabs[next]);tabs[next].focus();}};});
  document.addEventListener('visibilitychange',()=>{if(document.hidden)stop();});
})();
