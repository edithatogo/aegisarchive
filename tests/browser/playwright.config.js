const { defineConfig } = require('playwright/test');
const python = process.env.AEGIS_TEST_PYTHON || (process.platform === 'win32' ? 'python' : 'python3');
module.exports = defineConfig({
  testDir: '.', fullyParallel: false, workers: 1, timeout: 90000,
  expect: {timeout:30000},
  use: {headless: true, baseURL: 'http://127.0.0.1:8130',
    channel: process.env.AEGIS_BROWSER_CHANNEL || undefined,
    trace: 'retain-on-failure', screenshot: 'only-on-failure'},
  webServer: {cwd: require('node:path').resolve(__dirname, '../..'), command: `${python} cli/launch.py --no-browser --port 8130`,
    url: 'http://127.0.0.1:8130/__station/status', reuseExistingServer: false}
});
