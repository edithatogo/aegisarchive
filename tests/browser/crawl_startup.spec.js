const {test,expect}=require('playwright/test');
test('cold console initializes its complete dependency chain before enabling controls',async({browser})=>{
  for(let i=0;i<3;i++) {
    const context=await browser.newContext();
    const page=await context.newPage(),errors=[];
    page.on('pageerror',error=>errors.push(error.message));
    page.on('requestfailed',request=>errors.push(request.url()));
    await page.goto('/index.html');
    expect(await page.evaluate(()=>window.aegisReady)).toBe(true);
    expect(await page.evaluate(()=>({core:typeof CoreCrawler,native:typeof NativeCapture,debug:typeof DebugRecorder,rules:typeof CrawlRules,profile:activeProfile?.profile_id})))
      .toMatchObject({core:'function',native:'function',debug:'function',rules:'object',profile:'default_polite'});
    expect(errors).toEqual([]);
    await expect(page.locator('.container')).not.toHaveAttribute('inert','');
    await context.close();
  }
});
test('missing local dependency keeps controls inactive and reports a startup failure',async({page})=>{
  await page.route('**/lib/crawl_rules.js',route=>route.fulfill({status:404,body:'synthetic missing component'}));
  await page.goto('/index.html');
  expect(await page.evaluate(()=>window.aegisReady)).toBe(false);
  await expect(page.locator('#startupStatus')).toContainText('Unable to load');
  await expect(page.locator('.container')).toHaveAttribute('inert','');
  expect(await page.evaluate(()=>typeof activeProfile)).toBe('undefined');
});
for(const body of ['', 'throw new Error("synthetic execution failure")']) {
  test('HTTP200 dependency without successful execution stays inactive: '+(body?'throws':'missing export'),async({page})=>{
    await page.route('**/lib/crawl_rules.js',route=>route.fulfill({status:200,contentType:'application/javascript',body}));
    await page.goto('/index.html');
    expect(await page.evaluate(()=>window.aegisReady)).toBe(false);
    await expect(page.locator('#startupStatus')).toContainText('Unable to');
    await expect(page.locator('.container')).toHaveAttribute('inert','');
    expect(await page.evaluate(()=>typeof activeProfile)).toBe('undefined');
  });
}
