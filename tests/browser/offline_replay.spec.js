const { test, expect } = require('playwright/test');
test('fixture contract is deterministic and isolated', async ({ page }) => {
  const fixture = require('./fixtures/offline-site.json');
  expect(fixture.pages).toHaveLength(3);
  expect(fixture.assets).toContain('/site.css');
  expect(fixture.external).toMatch(/^https:\/\//);
  const unexpected = [];
  await page.route('**/*', route => { if (!route.request().url().startsWith('http://127.0.0.1')) unexpected.push(route.request().url()); return route.abort(); });
  await page.setContent('<a href="/second.html">Second</a><img src="/image.svg">');
  expect(unexpected).toEqual([]);
});
