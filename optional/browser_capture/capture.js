/** Optional, bounded Playwright adapter. Requires caller-provided Playwright. */
'use strict';

const { URL } = require('node:url');

function validateRecipe(recipe) {
  if (!recipe || typeof recipe.url !== 'string') throw new Error('recipe.url is required');
  const origin = new URL(recipe.url).origin;
  const maxPages = Math.min(Math.max(Number(recipe.maxPages || 1), 1), 25);
  const maxBytes = Math.min(Math.max(Number(recipe.maxBytes || 32 * 1024 * 1024), 1), 128 * 1024 * 1024);
  return { ...recipe, origin, maxPages, maxBytes, timeoutMs: Math.min(Math.max(Number(recipe.timeoutMs || 30000), 1000), 120000) };
}

async function capture(playwright, input) {
  const recipe = validateRecipe(input);
  const browser = await playwright.chromium.launch({ headless: input.headless !== false });
  const context = await browser.newContext(input.storageState ? { storageState: input.storageState } : {});
  const seen = []; let bytes = 0;
  await context.route('**/*', async route => {
    const request = route.request(); const target = new URL(request.url());
    if (target.origin !== recipe.origin || target.protocol !== 'http:' && target.protocol !== 'https:') return route.abort('blockedbyclient');
    await route.continue();
  });
  context.on('request', request => { if (new URL(request.url()).origin === recipe.origin) seen.push({ url: request.url(), method: request.method() }); });
  context.on('response', response => { if (new URL(response.url()).origin === recipe.origin) bytes += Number(response.headers()['content-length'] || 0); });
  const page = await context.newPage();
  await page.goto(recipe.url, { waitUntil: 'domcontentloaded', timeout: recipe.timeoutMs });
  for (let i = 0; i < (recipe.scrolls || 0); i++) await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  const rendered = await page.content();
  if (bytes > recipe.maxBytes) throw new Error('rendered capture byte limit exceeded');
  await browser.close();
  return { recipe: { origin: recipe.origin, maxPages: recipe.maxPages, maxBytes: recipe.maxBytes }, requests: seen, renderedHtml: rendered, bytes, derivative: { kind: 'rendered-dom', recipeVersion: 1 } };
}

module.exports = { capture, validateRecipe };
