import { defineConfig, devices } from 'playwright/test';
import { caseStudyViteMode } from './e2e/vite-release-environment';

const localChromium = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH;
const previewPort = process.env.SHOWCASE_E2E_PORT ?? '18473';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: 'list',
  outputDir: './node_modules/.cache/playwright-results',
  use: {
    baseURL: `http://127.0.0.1:${previewPort}`,
    browserName: 'chromium',
    launchOptions: localChromium ? { executablePath: localChromium } : {},
  },
  projects: [
    { name: 'desktop-chromium', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } } },
    { name: 'mobile-390x844', use: { ...devices['Desktop Chrome'], viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true } },
  ],
  webServer: {
    command: `node ./node_modules/vite/bin/vite.js --mode ${caseStudyViteMode} --host 127.0.0.1 --port ${previewPort} --strictPort`,
    url: `http://127.0.0.1:${previewPort}`,
    reuseExistingServer: false,
    timeout: 30_000,
  },
});
