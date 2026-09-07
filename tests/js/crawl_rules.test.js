const test = require('node:test');
const assert = require('node:assert/strict');
const {validateRules, evaluateRules} = require('../../web/lib/crawl_rules.js');

test('schema preserves ordered independent decisions', () => {
  const config = {version: 1, rules: [
    {id: 'files', match: {path_prefix: '/files/'}, decision: {download: true, traverse: false}},
    {id: 'rest', match: {}, decision: {discover: false}}
  ]};
  const before = JSON.stringify(config);
  assert.deepEqual(validateRules(config), config);
  assert.equal(JSON.stringify(config), before);
});
test('schema rejects unsafe or ambiguous rules', () => {
  for (const config of [
    {version: true, rules: []}, {version: 1, rules: [], extra: 1},
    ...[{regex: '(a+)+$'}, {max_depth: true}, {host: 'example.test.evil/'},
        {min_bytes: 4097, max_bytes: 4096}, {kind: 'script'}, {path_prefix: '/'+'x'.repeat(2048)}]
      .map(match => ({version: 1, rules: [{id: 'x', match, decision: {download: true}}]})),
    {version: 1, rules: [{id: 'x', match: {}, decision: {download: 1}}]}
  ]) assert.throws(() => validateRules(config));
});
test('schema rejects duplicates and too many rules', () => {
  const rule = {id: 'x', match: {}, decision: {download: true}};
  assert.throws(() => validateRules({version: 1, rules: [rule, rule]}));
  assert.throws(() => validateRules({version: 1, rules: Array.from({length:101}, (_,i)=>({...rule,id:String(i)}))}));
});
const resource = {url:'https://example.test/files/a.pdf',kind:'asset',depth:2};
test('first rule wins but cannot expand caller scope', () => {
  const config={version:1,rules:[
    {id:'files',match:{host:'example.test',path_prefix:'/files/'},decision:{traverse:false}},
    {id:'rest',match:{},decision:{discover:false}}]};
  assert.deepEqual(evaluateRules(config,resource,true),{discover:true,download:true,traverse:false,rule_id:'files',state:'decided',missing:[]});
  assert.equal(evaluateRules(config,resource,false).download,false);
});
test('unknown metadata cannot skip a potential deny', () => {
  const config={version:1,rules:[{id:'large',match:{min_bytes:10,mime:'application/pdf'},decision:{download:false}}]};
  const result=evaluateRules(config,resource,true);
  assert.equal(result.state,'needs_metadata');assert.equal(result.download,false);
  assert.deepEqual(result.missing,['bytes','mime']);
  assert.equal(evaluateRules(config,{...resource,bytes:10,mime:'application/pdf'},true).traverse,false);
  assert.equal(evaluateRules(config,{...resource,bytes:9},true).download,true);
});
test('invalid resources fail closed', () => {
  for(const change of [{url:'file:///tmp/a'},{url:'https://user:secret@example.test/'},{depth:true}])
    assert.throws(()=>evaluateRules({version:1,rules:[]},{...resource,...change},true));
});
