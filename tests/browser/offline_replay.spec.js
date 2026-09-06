const { test, expect } = require('playwright/test');
test('fixture contract is deterministic and isolated', async () => {
  const fixture = require('./fixtures/offline-site.json');
  expect(fixture.pages).toHaveLength(3);
  expect(fixture.assets).toContain('/site.css');
  expect(fixture.external).toMatch(/^https:\/\//);
});
