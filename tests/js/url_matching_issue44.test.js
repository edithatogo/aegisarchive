const test=require('node:test'); const assert=require('node:assert/strict');
const Reader=require('../../web/lib/warc_reader.js');
test('reader lookup uses stable query identity',()=>{
 const r=new Reader(); r.recordsByUrl.set('https://x.test/a?a=&b=2', {url:'https://x.test/a?a=&b=2'});
 assert.ok(r.getRecord('https://x.test/a?b=2&a=#frag'));
});
