const {test,expect}=require('playwright/test');
const fs=require('node:fs/promises');
const path=require('node:path');
const os=require('node:os');
const {spawnSync,spawn}=require('node:child_process');
const crypto=require('node:crypto');
const http=require('node:http');
const python=process.env.AEGIS_TEST_PYTHON || (process.platform==='win32'?'python':'python3');
const root=path.resolve(__dirname,'../..');

async function ordinaryLauncher(directory) {
  const temporary=await fs.realpath(await fs.mkdtemp(path.join(os.tmpdir(),'aegis relocated ')));
  const bundle=path.join(temporary,'Aegis Archive');
  let child,exited,output='';
  const close=async()=>{
    if(child?.pid && child.exitCode===null && child.signalCode===null){
      if(process.platform==='win32') {
        const killed=spawnSync('taskkill',['/PID',String(child.pid),'/T','/F'],{encoding:'utf8'});
        if(killed.status!==0 && child.exitCode===null) throw Error('Could not stop owned launcher process');
      } else child.kill('SIGTERM');
      await exited;
    }
    await fs.rm(temporary,{recursive:true,force:true});
  };
  try {
    const listed=spawnSync('git',['ls-files','-z'],{cwd:root,encoding:'utf8'});
    expect(listed.status,listed.stderr).toBe(0);
    const files={};
    for(const name of listed.stdout.split('\0').filter(Boolean)){
      expect(path.isAbsolute(name) || name.split('/').includes('..')).toBe(false);
      const source=path.join(root,name),target=path.join(bundle,name);
      expect((await fs.lstat(source)).isFile()).toBe(true);
      await fs.mkdir(path.dirname(target),{recursive:true});
      await fs.copyFile(source,target);
      const original=await fs.readFile(source),copied=await fs.readFile(target);
      expect(copied.equals(original),name).toBe(true);
      files[name]=crypto.createHash('sha256').update(copied).digest('hex');
    }
    const windows=process.platform==='win32';
    const name=windows?'START_WINDOWS.cmd':process.platform==='darwin'?'START_MAC.command':'START_LINUX.sh';
    const launcher=path.join(bundle,name);
    // Generated POSIX packages need an executable entrypoint. No source bytes
    // or checkout permissions are changed; record this packaging prerequisite.
    if(!windows) await fs.chmod(launcher,0o755);
    const launch=(environment,diagnostic=false)=>{
      const options={cwd:bundle,env:environment,encoding:'utf8'};
      const executable=windows?(process.env.ComSpec || 'C:\\Windows\\System32\\cmd.exe'):launcher;
      const args=windows?['/d','/s','/c',`""${launcher}" --no-browser"`]:[];
      if(windows) options.windowsVerbatimArguments=true;
      return diagnostic?spawnSync(executable,args,{...options,input:'\n',timeout:5000}):spawn(executable,args,options);
    };
    const emptyPath=path.join(temporary,'no runtime');
    await fs.mkdir(emptyPath);
    if(!windows) await fs.symlink('/usr/bin/dirname',path.join(emptyPath,'dirname'));
    const missing=launch({...process.env,PATH:emptyPath},true);
    expect(missing.error?.message).toBeUndefined();
    const diagnostic=(missing.stdout || '')+(missing.stderr || '');
    expect(diagnostic).toContain(windows?'bundled Python is missing':'Python 3 was not found');
    await fs.writeFile(path.join(directory,'launcher-missing-runtime.txt'),diagnostic);
    const occupied=await new Promise(resolve=>{
      const request=http.get('http://127.0.0.1:8000/__station/status',response=>{
        let text='';response.on('data',data=>{text+=data;});
        response.on('end',()=>{try{resolve(JSON.parse(text).station==='aegisarchive');}catch(_){resolve(false);}});
      });
      request.on('error',()=>resolve(false));
      request.setTimeout(1000,()=>{request.destroy();resolve(false);});
    });
    expect(occupied,'An existing default-port station must not substitute for the relocated launcher').toBe(false);
    child=launch({...process.env,PYTHONUNBUFFERED:'1',BROWSER:windows?'': '/usr/bin/true'});
    exited=new Promise(resolve=>child.once('close',resolve));
    child.stdout.on('data',data=>{output+=data.toString();});
    child.stderr.on('data',data=>{output+=data.toString();});
    let startupError;
    child.on('error',error=>{startupError=error;});
    await expect.poll(()=>{
      if(startupError) throw startupError;
      if(child.exitCode!==null) throw Error('Ordinary launcher exited before readiness: '+output);
      return /Local Web Console:\s+(http:\/\/127\.0\.0\.1:\d+)\/index\.html/.exec(output)?.[1] || null;
    }).not.toBeNull();
    const origin=/Local Web Console:\s+(http:\/\/127\.0\.0\.1:\d+)\/index\.html/.exec(output)[1];
    await fs.writeFile(path.join(directory,'launcher-manifest.json'),JSON.stringify({
      bundle,launcher:name,source_files:files,posix_executable_prepared:!windows,pid:child.pid,origin},null,2)+'\n');
    await fs.writeFile(path.join(directory,'launcher-startup.txt'),output);
    return {origin,bundle,close};
  } catch(error) {
    // Failed readiness must retain the child's output too, not just the poll
    // timeout. Do not guess which launcher/startup stage blocked on a runner.
    error.message+='\nOrdinary launcher output:\n'+output;
    try {
      await fs.writeFile(path.join(directory,'launcher-startup.txt'),output);
      if(process.platform==='darwin' && child?.pid && child.exitCode===null && child.signalCode===null){
        // Sample only our still-live launcher before cleanup. This is failure
        // evidence, not a readiness retry or an extension of its deadline.
        const processState=spawnSync('/bin/ps',['-p',String(child.pid),'-o','pid,ppid,state,etime,command'],{encoding:'utf8',timeout:2000});
        const sample=spawnSync('/usr/bin/sample',[String(child.pid),'1','1','-file',path.join(directory,'launcher-stack.txt')],{encoding:'utf8',timeout:5000});
        const result=value=>({status:value.status,signal:value.signal,error:value.error?.message || null,stdout:value.stdout || '',stderr:value.stderr || ''});
        await fs.writeFile(path.join(directory,'launcher-process.json'),JSON.stringify({pid:child.pid,process:result(processState),sample:result(sample)},null,2)+'\n');
      }
    } catch(diagnosticError) {
      error.message+='\nCould not retain launcher output: '+diagnosticError.message;
    } finally {
      try {await close();} catch(cleanupError) {
        error.message+='\nLauncher cleanup failed: '+cleanupError.message;
      }
    }
    throw error;
  }
}
test('an unexecuted receipt cannot qualify a mirroring platform',async()=>{
  const dir=await fs.mkdtemp(path.join(os.tmpdir(),'aegis receipt contract '));
  try {
    const output=path.join(dir,'pending.json');
    const result=spawnSync(python,['scripts/mirroring_acceptance.py','--output',output],{cwd:root,encoding:'utf8'});
    expect(result.status,result.stderr).toBe(0);
    const receipt=JSON.parse(await fs.readFile(output,'utf8'));
    expect(receipt.schema).toBe('aegis.mirroring-acceptance.v2');
    expect(receipt.qualification_status).toBe('pending');
    const fixture=JSON.parse(await fs.readFile(path.join(__dirname,'fixtures/mirroring-site.json'),'utf8'));
    expect(receipt.fixture_hashes).toEqual(Object.fromEntries(Object.entries(fixture).map(([name,value])=>[name,crypto.createHash('sha256').update(value.body).digest('hex')])));
    expect(receipt.offline).toBeNull();
    const checked=spawnSync(python,['scripts/mirroring_acceptance.py','--check','--output',output],{cwd:root,encoding:'utf8'});
    expect(checked.status).not.toBe(0);
    receipt.qualification_status='passed';
    await fs.writeFile(output,JSON.stringify(receipt));
    const forged=spawnSync(python,['scripts/mirroring_acceptance.py','--check','--output',output],{cwd:root,encoding:'utf8'});
    expect(forged.status).not.toBe(0);
  } finally {await fs.rm(dir,{recursive:true,force:true});}
});
test('fixture payload identities are deterministic and include real CSS and image bytes',async()=>{
  const fixture=JSON.parse(await fs.readFile(path.join(__dirname,'fixtures/mirroring-site.json'),'utf8'));
  expect(Object.keys(fixture)).toContain('/site.css');expect(Object.keys(fixture)).toContain('/asset.svg');
  const hashes=Object.fromEntries(Object.entries(fixture).map(([name,value])=>[name,crypto.createHash('sha256').update(value.body).digest('hex')]));
  expect(hashes['/site.css']).toMatch(/^[a-f0-9]{64}$/);
  expect(fixture['/asset.svg'].body).toContain('width="12"');
  expect(fixture['/second.html'].body).toContain('/third.html');
});

test('measured capture reload recovery and disconnected replay',async({page,browser},testInfo)=>{
  test.setTimeout(90000);
  const fixture=JSON.parse(await fs.readFile(path.join(__dirname,'fixtures/mirroring-site.json'),'utf8'));
  const directory=path.join(root,'artifacts',`mirroring-${process.platform}-${process.arch}`);
  await fs.mkdir(directory,{recursive:true});
  const hash=bytes=>crypto.createHash('sha256').update(bytes).digest('hex');
  const command=(args)=>{
    const result=spawnSync(python,args,{cwd:root,encoding:'utf8',timeout:10000});
    expect(result.error?.message || result.stderr || result.stdout).toBeDefined();
    expect(result.status,result.stderr || result.stdout).toBe(0);
    return result.stdout;
  };
  const snapshot=()=>JSON.parse(command(['scripts/mirroring_acceptance.py','--snapshot']));
  const observations={schema:'aegis.mirroring-observations.v2',source_before:snapshot(),
    source_after:null,runtime:JSON.parse(command(['-c','import json,platform; print(json.dumps(dict(system=platform.system(),machine=platform.machine(),python=platform.python_version())))'])),
    capture:null,offline:null,authentication:null,recovery:null,launcher:null,artifacts:{}};
  observations.runtime.browser={name:browser.browserType().name(),version:browser.version(),
    playwright_version:require('playwright/package.json').version};
  expect(observations.runtime.browser.playwright_version).toBe('1.63.0');
  const requests=[];
  const secret='synthetic-t2-cookie-value';
  let expired=false,holdSecond=false,heldResponse=null,closed=false,replayContext,station;
  let phase='source-start';
  const source=http.createServer((request,response)=>{
    const pathname=new URL(request.url,'http://127.0.0.1').pathname;
    requests.push({path:pathname,credential_present:!!(request.headers.cookie || request.headers.authorization)});
    const entry=fixture[pathname];
    const send=()=>{
      if (response.destroyed) return;
      if ((pathname==='/protected.html' || pathname==='/expires.html') &&
          (request.headers.cookie!==`session=${secret}` || expired)) {
        response.writeHead(401,{'Content-Type':'text/plain','Connection':'close'});response.end('Synthetic access denied');return;
      }
      if (pathname==='/protected.html') expired=true;
      response.writeHead(entry?200:404,{'Content-Type':entry?.mime || 'text/plain','Connection':'close'});
      response.end(entry?.body || 'Not captured');
    };
    if (pathname==='/second.html' && holdSecond && !heldResponse) heldResponse=send;
    else send();
  });
  const stopSource=async()=>{
    if (closed) return;
    heldResponse?.();holdSecond=false;
    await new Promise((resolve,reject)=>source.close(error=>error?reject(error):resolve()));
    closed=true;
  };
  const errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  const baseProfile=JSON.parse(await fs.readFile(path.join(root,'profiles/default_polite.json'),'utf8'));
  let origin;
  const profile=(authentication={mode:'none'})=>({...baseProfile,
    target:{...baseProfile.target,allowed_domains:['127.0.0.1'],max_pages:20,max_depth:5,
      seed_urls:{tier_1_core:[origin+'/index.html'],tier_2_breadth:[],tier_3_discovery:[]}},
    politeness:{...baseProfile.politeness,min_delay_ms:250,max_delay_ms:250,max_requests_per_minute:300,concurrency:1},
    authentication});
  const upload=async configured=>{
    await page.locator('#profileFileInput').setInputFiles({name:'synthetic-mirroring.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(configured))});
    await expect.poll(()=>page.evaluate(()=>activeProfile.profile_id)).toBe(configured.profile_id);
    // FileReader is asynchronous; compare the full imported profile before starting.
    await expect.poll(()=>page.evaluate(()=>JSON.stringify(activeProfile))).toBe(JSON.stringify(configured));
    await page.locator('#captureRoute').selectOption('native');
  };
  const boot=async()=>{
    await page.goto(station.origin+'/index.html');
    expect(await page.evaluate(()=>window.aegisReady)).toBe(true);
  };
  const authConfig=expires=>({mode:'browser_session',allowed_domains:['127.0.0.1'],
    source:JSON.stringify({cookies:[{name:'session',value:secret,domain:'127.0.0.1',path:'/',expires}]})});
  try {
    phase='relocated-ordinary-launcher';
    station=await ordinaryLauncher(directory);
    expect(station.bundle).toContain(' ');
    const status=await page.request.get(station.origin+'/__station/status');
    const runtime=await status.json();
    expect(runtime.station).toBe('aegisarchive');
    expect(runtime.python).toBe(observations.runtime.python);
    expect(runtime.platform).toBe(observations.runtime.system);
    observations.launcher={ordinary:true,relocated:true,missing_runtime_diagnostic:true};
    await new Promise(resolve=>source.listen(0,'127.0.0.1',resolve));
    origin=`http://127.0.0.1:${source.address().port}`;
    phase='denied-without-session';await boot();
    await upload(profile());
    await page.locator('#simpleTarget').fill(origin+'/protected.html');
    await page.locator('#btnStart').click();
    await expect(page.locator('#captureState')).toHaveText('FAILED — no responses saved');
    await expect(page.locator('#logContainer')).toContainText('HTTP 401');
    expect(requests.filter(r=>r.path==='/protected.html')).toEqual([{path:'/protected.html',credential_present:false}]);
    phase='expired-client-session';
    await upload(profile(authConfig(1)));
    await page.locator('#btnStart').click();
    await expect(page.locator('#captureState')).toHaveText('FAILED — no responses saved');
    await expect(page.locator('#logContainer')).toContainText('HTTP 401');
    expect(requests.filter(r=>r.path==='/protected.html')).toEqual([
      {path:'/protected.html',credential_present:false},{path:'/protected.html',credential_present:false}]);

    phase='capture-to-checkpoint';
    const configured=profile(authConfig(-1));
    await upload(configured);
    await page.locator('#simpleTarget').fill('');
    holdSecond=true;
    await page.locator('#btnStart').click();
    await expect.poll(()=>!!heldResponse).toBe(true);
    const saved=await page.evaluate(()=>({id:usbStorage.id,directory:usbStorage.directory,log:nativeCapture.logFile}));
    const checkpointPath=path.join(saved.directory,'checkpoint.json');
    let checkpoint;
    await expect.poll(async()=>{
      try {checkpoint=JSON.parse(await fs.readFile(checkpointPath,'utf8'));return checkpoint.prefixes.warc.bytes;}
      catch(error) {if(error.code==='ENOENT') return 0;throw error;}
    }).toBeGreaterThan(0);
    const prefix=(await fs.readFile(path.join(saved.directory,'archive.warc.partial'))).subarray(0,checkpoint.prefixes.warc.bytes);
    expect(hash(prefix)).toBe(checkpoint.prefixes.warc.sha256);
    expect(prefix.toString()).toContain('Index fixture');
    expect(JSON.stringify(checkpoint)).not.toContain(secret);
    expect(requests.filter(r=>r.path==='/index.html')).toHaveLength(1);

    phase='reload-and-resume';
    await page.reload();
    expect(await page.evaluate(()=>window.aegisReady)).toBe(true);
    heldResponse();holdSecond=false;
    await expect(page.locator('#resumeBanner')).toBeVisible();
    await expect(page.locator(`#resumeArchive option[value="${saved.id}"]`)).toHaveCount(1);
    await upload(configured);
    await page.locator('#resumeArchive').selectOption(saved.id);
    // A successful reopen consumes a generation even when native setup fails.
    // Retry must rediscover that generation and retain this archive, not start over.
    await page.route('**/__station/capture/start',route=>route.fulfill({status:503,
      contentType:'application/json',body:JSON.stringify({error:'Synthetic setup interruption'})}));
    await page.locator('#resumeBanner').getByRole('button',{name:'▶️ Resume',exact:true}).click();
    await expect(page.locator('#captureOutcome')).toContainText('Synthetic setup interruption');
    await expect(page.locator('#resumeBanner')).toBeVisible();
    await expect(page.locator('#resumeArchive')).toHaveValue(saved.id);
    await page.unroute('**/__station/capture/start');
    await page.locator('#resumeBanner').getByRole('button',{name:'▶️ Resume',exact:true}).click();
    await expect(page.locator('#captureState')).toContainText('INCOMPLETE');
    await expect.poll(()=>page.evaluate(()=>!!finalResults?.storageReceipt)).toBe(true);
    const result=await page.evaluate(()=>({receipt:finalResults.storageReceipt,report:currentReportJSON,log:nativeCapture.logFile}));
    expect(result.receipt.warc_path.startsWith(station.bundle+path.sep)).toBe(true);
    const warc=await fs.readFile(result.receipt.warc_path);
    const cdx=await fs.readFile(result.receipt.cdx_path);
    expect(warc.subarray(0,prefix.length).equals(prefix)).toBe(true);
    expect(requests.filter(r=>r.path==='/index.html')).toHaveLength(1);
    expect(requests.filter(r=>r.path==='/protected.html')).toHaveLength(3);
    expect(requests.filter(r=>r.path==='/protected.html').at(-1).credential_present).toBe(true);
    expect(requests.filter(r=>r.path==='/expires.html')).toEqual([{path:'/expires.html',credential_present:true}]);
    await expect(page.locator('#logContainer')).toContainText('HTTP 401');
    expect(result.receipt.archive_id).toBe(saved.id);
    expect(warc.length).toBeGreaterThan(prefix.length);
    for (const raw of [warc.toString(),cdx.toString(),result.report,
      await fs.readFile(saved.log,'utf8'),await fs.readFile(result.log,'utf8')]) expect(raw).not.toContain(secret);
    observations.authentication={denied:true,expired:true,redacted:true};
    observations.recovery={interrupted:true,resumed:true,bytes_preserved:true,reload_recovered:true,mode:'durable_reload_resume'};
    await fs.copyFile(result.receipt.warc_path,path.join(directory,'capture.warc'));
    await fs.copyFile(result.receipt.cdx_path,path.join(directory,'capture.cdx'));
    for(const [kind,bytes] of [['warc',warc],['cdx',cdx]]) observations.artifacts[kind]={path:`capture.${kind}`,sha256:hash(bytes),bytes:bytes.length};
    phase='archive-verification';
    const verified=command(['cli/warc_verify.py',path.join(directory,'capture.warc'),'--cdx',path.join(directory,'capture.cdx')]);
    await fs.writeFile(path.join(directory,'verifier.txt'),verified);

    phase='browser-readback';
    replayContext=await browser.newContext({baseURL:station.origin});
    const viewer=await replayContext.newPage();
    viewer.on('pageerror',error=>errors.push(error.message));
    await viewer.goto('/viewer.html');
    await viewer.locator('#warcFileInput').setInputFiles(path.join(directory,'capture.warc'));
    await expect(viewer.locator('#recordCountLabel')).toContainText('records loaded');
    const payloads=await viewer.evaluate(async()=>{
      const values={};
      for(const [url,record] of reader.recordsByUrl){
        const digest=await crypto.subtle.digest('SHA-256',record.bodyBytes);
        values[new URL(url).pathname]={status:record.status,sha256:[...new Uint8Array(digest)].map(n=>n.toString(16).padStart(2,'0')).join('')};
      }
      return values;
    });
    const captured=['/index.html','/second.html','/third.html','/site.css','/asset.svg','/protected.html'];
    for(const name of captured) expect(payloads[name]).toEqual({status:200,sha256:hash(Buffer.from(fixture[name].body))});
    observations.capture={responses:Object.keys(payloads).length,warc_verified:true,expected_payload_hashes_verified:true};
    await fs.writeFile(path.join(directory,'payload-readback.json'),JSON.stringify(payloads,null,2)+'\n');

    phase='disconnect-source';
    await page.close();
    await stopSource();
    const unreachable=await new Promise(resolve=>{
      const request=http.get(origin+'/index.html',response=>{response.resume();resolve(false);});
      request.on('error',error=>resolve(error.code==='ECONNREFUSED'));
      request.setTimeout(1500,()=>{request.destroy();resolve(false);});
    });
    expect(unreachable).toBe(true);
    const sourceCount=requests.length,unexpected=[];
    viewer.on('request',request=>{if(/^https?:/.test(request.url())) unexpected.push(request.url());});
    await replayContext.setOffline(true);
    phase='offline-real-navigation';
    let visits=0;
    const frame=viewer.frameLocator('#replayFrame');
    const assertPage=async heading=>{
      await expect(frame.getByRole('heading',{name:heading,exact:true})).toBeVisible();
      await expect(frame.locator('body')).toHaveCSS('color','rgb(1, 2, 3)');
      await expect.poll(()=>frame.locator('#fixture-image').evaluate(image=>[image.complete,image.naturalWidth,image.naturalHeight])).toEqual([true,12,8]);
      expect(await frame.locator('body').evaluate(()=>window.sourceScriptExecuted)).toBeUndefined();
      visits++;
    };
    await assertPage('Index fixture');
    for(let cycle=0;cycle<2;cycle++){
      await frame.getByRole('link',{name:'Second page',exact:true}).click();await assertPage('Second fixture');
      await frame.getByRole('link',{name:'Third page',exact:true}).click();await assertPage('Third fixture');
      await frame.getByRole('link',{name:'Index page',exact:true}).click();await assertPage('Index fixture');
    }
    await viewer.getByRole('button',{name:'Back',exact:true}).click();await assertPage('Third fixture');
    await viewer.getByRole('button',{name:'Forward',exact:true}).click();await assertPage('Index fixture');
    await frame.getByRole('link',{name:'Second page',exact:true}).click();await assertPage('Second fixture');
    await frame.getByRole('link',{name:'Third page',exact:true}).click();await assertPage('Third fixture');
    await frame.getByRole('link',{name:'Missing page',exact:true}).click();
    await expect(viewer.locator('#activeUrlDisplay')).toContainText('Missing archived resource:');
    await expect(frame.getByRole('heading',{name:'Third fixture',exact:true})).toBeVisible();
    expect(requests.length).toBe(sourceCount);
    expect(unexpected).toEqual([]);expect(errors).toEqual([]);
    observations.offline={source_stopped:true,source_unreachable:true,navigation_visits:visits,
      links_verified:true,css_verified:true,image_verified:true,unexpected_requests:unexpected.length,
      source_requests:requests.length-sourceCount,page_errors:errors.length};
    phase='measured-observations-complete';
  } finally {
    heldResponse?.();holdSecond=false;
    await replayContext?.close();
    if(source.listening) await stopSource();
    await page.close();
    await station?.close();
    observations.source_after=snapshot();
    await fs.writeFile(path.join(directory,'source-requests.json'),JSON.stringify(requests,null,2)+'\n');
    await fs.writeFile(path.join(directory,'run-state.json'),JSON.stringify({phase,page_errors:errors},null,2)+'\n');
    await fs.writeFile(path.join(directory,'observations.json'),JSON.stringify(observations,null,2)+'\n');
    await testInfo.attach('mirroring-run-state',{path:path.join(directory,'run-state.json'),contentType:'application/json'});
  }
  // Dirty development evidence cannot qualify a platform. A clean committed run
  // must pass every real assertion before its receipt may qualify this machine.
  command(['scripts/mirroring_acceptance.py','--output',path.join(directory,'receipt.json'),
    '--observations',path.join(directory,'observations.json')]);
  const receipt=JSON.parse(await fs.readFile(path.join(directory,'receipt.json'),'utf8'));
  expect(observations.launcher).toEqual({ordinary:true,relocated:true,missing_runtime_diagnostic:true});
  expect(receipt.qualification_status).toBe(observations.source_before.worktree_clean?'passed':'failed');
});
