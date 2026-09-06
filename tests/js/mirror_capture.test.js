const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {createHash} = require('node:crypto');
const fixtureDir = path.join(__dirname, '../fixtures/mirror');
const manifest = JSON.parse(fs.readFileSync(path.join(fixtureDir, 'manifest.json')));
test('frozen resource bytes agree with manifest', () => {
  assert.equal(manifest.resources.length, 9);
  for (const r of manifest.resources) assert.equal(createHash('sha256').update(fs.readFileSync(path.join(fixtureDir, r.file))).digest('hex'), r.sha256);
});

test('HTML discovery parity vectors', () => {
  const {discover} = require('../../web/lib/mirror_resources.js');
  for (const v of JSON.parse(fs.readFileSync(path.join(fixtureDir, 'discovery.json')))) {
    assert.deepEqual(discover(v.text, v.mime, v.url).resources.map(x => x.url), v.expected);
  }
});
