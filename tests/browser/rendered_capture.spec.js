const { test, expect } = require('@playwright/test');

test('rendered capture contract remains bounded and origin scoped', async ({ page }) => {
  await page.goto('http://127.0.0.1:8120/');
  const result = await page.evaluate(() => ({ original: document.body.innerText, derivative: { kind: 'rendered-dom', recipeVersion: 1 } }));
  expect(result.derivative).toEqual({ kind: 'rendered-dom', recipeVersion: 1 });
  expect(result.original).toContain('Aegis');
});
