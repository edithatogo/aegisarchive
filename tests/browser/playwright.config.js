const { defineConfig } = require('playwright/test');
module.exports = defineConfig({ testDir: '.', fullyParallel: false, use: { headless: true }, webServer: undefined });
