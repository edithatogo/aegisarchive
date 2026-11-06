const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const {NativeCapture}=require('../../web/lib/native_capture.js');
test('resume restores public settings while preserving freshly imported authentication',async()=>{
 const authentication={mode:'basic_env',allowed_domains:['fixture.invalid'],source:'FIXTURE_AUTH'};
 const profile={profile_id:'fixture',politeness:{},target:{allowed_domains:['fixture.invalid']},authentication:{mode:'basic_env',allowed_domains:['fixture.invalid']}};
 const hash=await NativeCapture.profileHash({...profile,authentication});
 const archive={archive_id:'fixture',profile_hash:hash};
 const elements=new Map();const element=id=>{if(!elements.has(id))elements.set(id,{value:id==='resumeArchive'?'fixture':'',style:{}});return elements.get(id);};
 let started=false;
 const context={recoveryArchives:[archive],pendingArchive:null,activeProfile:{authentication},NativeCapture,
  document:{getElementById:element},fetch:async()=>({ok:true,json:async()=>({fixture:{profile,route:'native'}})}),updateProfileDisplay(){},startHarvest:async()=>{started=true;}};
 const html=fs.readFileSync(require.resolve('../../web/index.html'),'utf8');
 const source=html.slice(html.indexOf('    async function resumeFromCheckpoint()'),html.indexOf('    function discardCheckpoint()'));
 vm.createContext(context);vm.runInContext(source,context);await context.resumeFromCheckpoint();
 assert.equal(started,true);assert.equal(context.activeProfile.authentication,authentication);
 assert.equal(element('simpleTarget').value,'');assert.equal(element('captureRoute').value,'native');
});
