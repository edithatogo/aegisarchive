const { defineConfig } = require('playwright/test');
module.exports = defineConfig({ testDir: '.', fullyParallel: false, use: { headless: true, launchOptions: { executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' } }, webServer: undefined });
