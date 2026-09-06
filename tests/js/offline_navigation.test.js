const test = require('node:test');
const assert = require('node:assert/strict');
const nav = require('../../web/lib/offline_navigation.js');

test('canonical navigation preserves query identity and removes fragments', () => {
  assert.equal(nav.canonical('../page.html?edition=2#intro', 'https://archive.test/site/index.html'), 'https://archive.test/page.html?edition=2');
  assert.equal(nav.canonical('https://user:pass@archive.test/x', 'https://archive.test/'), null);
});
test('resolution is archive-local and reports missing destinations', () => {
  const reader = {getRecord: url => url.endsWith('/ok.html') ? {url} : null};
  assert.equal(nav.resolve('/ok.html#x', 'https://archive.test/', reader).state, 'captured');
  assert.equal(nav.resolve('/missing.html', 'https://archive.test/', reader).state, 'missing');
});
test('navigation messages require source and nonce binding', () => {
  const source = {}; const msg = nav.navigationMessage('https://archive.test/a', 'n');
  assert.equal(nav.acceptNavigation({source, data:msg}, source, 'n'), true);
  assert.equal(nav.acceptNavigation({source:{}, data:msg}, source, 'n'), false);
  assert.equal(nav.acceptNavigation({source, data:{...msg, nonce:'x'}}, source, 'n'), false);
});
test('replay rewrites captured style resources and never falls back live', () => {
  const WarcReader = require('../../web/lib/warc_reader.js');
  const reader = new WarcReader();
  const image = {url:'https://archive.test/image.svg', bodyBytes:new Uint8Array([1]), mimeType:'image/svg+xml'};
  reader.recordsByUrl.set(reader.normalizeUrl(image.url), image);
  const css = reader.rewriteStyles('body{background:url("/image.svg")}x{background:url(/missing.svg)}','https://archive.test/index.html');
  assert.match(css, /blob:/);
  assert.match(css, /data:,/);
});
