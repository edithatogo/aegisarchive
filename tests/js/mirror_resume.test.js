const test = require('node:test');
const assert = require('node:assert/strict');
const Checkpoint = require('../../web/lib/mirror_checkpoint.js');
test('checkpoint metadata validates and lineage marks revisits', () => {
  const s = {version:1, profile_id:'p', profile_sha256:'a'.repeat(64), queue:[], visited:[], segments:[
    {sequence:0,name:'segment-00000000.bin',bytes:1,sha256:'b'.repeat(64)},
    {sequence:1,name:'segment-00000001.bin',bytes:1,sha256:'b'.repeat(64)}]};
  assert.equal(Checkpoint.validate(s,'p','a'.repeat(64)), true);
  assert.equal(Checkpoint.lineage(s.segments)[1].revisit, true);
  assert.equal(Checkpoint.validate({...s, profile_id:'x'},'p','a'.repeat(64)), false);
  assert.equal(Checkpoint.validate({...s, segments:[{...s.segments[0],name:'../secret'}]},'p','a'.repeat(64)), false);
});
