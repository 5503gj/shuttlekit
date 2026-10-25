const assert=require('node:assert/strict'),path=require('node:path'),net=require('node:net'),fs=require('node:fs/promises');
const {spawn}=require('node:child_process'),{chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
(async()=>{
  const sock=net.createServer();await new Promise(resolve=>sock.listen(0,'127.0.0.1',resolve));const port=sock.address().port;await new Promise(resolve=>sock.close(resolve));
  const server=spawn(process.env.PYTHON||'python',['-u','speed_api.py'],{cwd:path.resolve(__dirname,'..'),env:{...process.env,PORT:String(port),HOST:'127.0.0.1'},stdio:'ignore'});let browser;
  try{
    let ready=false;for(let i=0;i<100;i++){try{if((await fetch(`http://127.0.0.1:${port}/api/health`)).ok){ready=true;break;}}catch{}await new Promise(resolve=>setTimeout(resolve,100));}assert.ok(ready);
    browser=await chromium.launch({headless:true,...(process.env.CHROMIUM_PATH?{executablePath:process.env.CHROMIUM_PATH}:{})});
    const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',error=>errors.push(error.message));
    await page.goto(`http://127.0.0.1:${port}/`);await page.locator('#coachRun').click();assert.match(await page.locator('#coachStatus').innerText(),/先创建/);
    await page.locator('#createBtn').click();await page.waitForFunction(()=>state.socket?.readyState===1);
    await page.locator('.shot-button').first().click();await page.waitForFunction(()=>state.snapshot?.sample_count===7&&!state.simulating);
    assert.match(await page.locator('#sourceLabel').innerText(),/模拟/);
    await page.locator('#coachGoal').selectOption('control');await page.locator('#coachRun').click();await page.waitForFunction(()=>!document.querySelector('#coachResult').hidden);
    assert.equal(await page.locator('#coachTools li').count(),4);assert.equal(await page.locator('#coachPlan input').count(),4);
    assert.match(await page.locator('#coachLimits').innerText(),/不能评价运动能力/);
    assert.ok((await page.locator('#trajectoryPath').getAttribute('d')).includes('L'));
    const lastPosition=await page.locator('#trajectoryCursor').getAttribute('cx');
    await page.locator('#replayRange').focus();await page.locator('#replayRange').press('Home');
    assert.notEqual(await page.locator('#trajectoryCursor').getAttribute('cx'),lastPosition);
    await page.locator('#replayBtn').click();await page.waitForFunction(()=>document.querySelector('#replayRange').value==='7');
    await page.locator('#coachPlan input').first().check();assert.match(await page.locator('#planProgress').innerText(),/1 \/ 4/);
    const [download]=await Promise.all([page.waitForEvent('download'),page.locator('#exportJson').click()]);
    const report=JSON.parse(await fs.readFile(await download.path(),'utf8'));
    assert.equal(report.points.length,8);assert.equal(report.source,'simulated');assert.equal(report.goal,'control');assert.equal(report.completed_task_ids.length,1);
    const credentials=await page.evaluate(()=>[state.token,state.readToken]);assert.ok(credentials.every(token=>!JSON.stringify(report).includes(token)));
    for(const width of [1440,768,390]){await page.setViewportSize({width,height:900});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);}
    await page.emulateMedia({reducedMotion:'reduce'});assert.equal(await page.locator('#coachTools li').first().evaluate(node=>getComputedStyle(node).animationName),'none');
    const link=await page.evaluate(()=>location.origin+'/?session='+state.sessionId+'#read='+state.readToken),display=await browser.newPage();display.on('pageerror',error=>errors.push(error.message));
    await display.goto(link);await display.waitForFunction(()=>state.readOnly);await display.locator('#coachRun').click();await display.waitForFunction(()=>!document.querySelector('#coachResult').hidden);assert.ok(await display.locator('#resetBtn').isDisabled());
    await page.route('**/coach?*',async route=>{await new Promise(resolve=>setTimeout(resolve,500));await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({...report,observations:['stale-response-must-not-appear']})}).catch(()=>{});});
    await page.locator('#coachRun').click();await page.locator('#coachCancel').click();await page.waitForTimeout(700);assert.match(await page.locator('#coachStatus').innerText(),/已取消/);assert.doesNotMatch(await page.locator('#coachObservations').innerText(),/stale-response/);
    await page.unroute('**/coach?*');await page.route('**/coach?*',route=>route.fulfill({status:403,body:'{}'}));await page.locator('#coachRun').click();await page.waitForFunction(()=>document.querySelector('#coachStatus').textContent.includes('无法读取'));await page.unroute('**/coach?*');
    await page.locator('#resetBtn').click();await page.waitForFunction(()=>document.querySelector('#coachResult').hidden);assert.equal(await page.locator('#trajectoryPath').getAttribute('d'),'');
    await page.locator('#pxPerMeter').fill('');await page.locator('#createBtn').click();await page.waitForFunction(()=>state.snapshot?.px_per_meter===null&&state.socket?.readyState===1);
    await page.locator('.shot-button').first().click();await page.waitForFunction(()=>state.snapshot?.last_point?.timestamp&&!state.simulating);await page.locator('#coachRun').click();await page.waitForFunction(()=>!document.querySelector('#coachResult').hidden);
    assert.equal(await page.locator('#currentSpeed').innerText(),'—');assert.match(await page.locator('#coachObservations').innerText(),/px\/s/);assert.match(await page.locator('#chartUnit').innerText(),/px\/s/);
    await page.locator('#tab-equipment').focus();await page.locator('#tab-equipment').press('ArrowRight');assert.equal(await page.locator('#tab-history').getAttribute('aria-selected'),'true');
    assert.deepEqual(errors,[]);console.log('Coach browser passed: actual report, source flags, replay, completion export, readonly review, cancellation, errors, reset, unscaled units, responsive and reduced motion.');
  }finally{if(browser)await browser.close();server.kill();}
})().catch(error=>{console.error(error);process.exitCode=1;});
