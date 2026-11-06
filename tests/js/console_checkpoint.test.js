const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
test('checkpoint status handles finalization and only reports acknowledged saves',async()=>{
 const html=fs.readFileSync(require.resolve('../../web/index.html'),'utf8');
 const line=html.split('\n').find(x=>x.includes('onRecoveryCheckpoint: async state =>'));
 const expr=line.trim().replace(/^onRecoveryCheckpoint: /,'').replace(/,$/,'');
 const status={textContent:'previous'};let calls=0,fail=false;
 const context={usbStorage:{profileHash:'x',checkpoint:async()=>{calls++;if(fail)throw Error('write failed');}},document:{getElementById:()=>status},Date};
 const callback=vm.runInNewContext('('+expr+')',context);
 await callback(null);assert.equal(calls,1);assert.equal(status.textContent,'previous');
 const state={frontier:{visited:['one'],queue:['two','three']}};
 await callback(state);assert.match(status.textContent,/1 visited, 2 queued/);
 await callback({});assert.match(status.textContent,/\? visited, \? queued/);
 const saved=status.textContent;fail=true;await assert.rejects(callback(state));assert.equal(status.textContent,saved);
});
