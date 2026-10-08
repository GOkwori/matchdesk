/** Test the built Compose application, never a separately spawned dev server. */
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './specs',
  timeout: 30000,
  expect: { timeout: 7000 },
  forbidOnly: true,
  retries: 0, // Failures remain visible; reruns are separate recorded executions.
  workers: 1,
  outputDir: '../artifacts/integration/browser-results',
  reporter: [
    ['list'],
    ['junit', { outputFile: '../artifacts/integration/browser-junit.xml' }],
    ['json', { outputFile: '../artifacts/integration/browser-results.json' }],
    ['html', { outputFolder: '../artifacts/integration/browser-report', open: 'never' }],
  ],
  use: {
    baseURL: 'http://127.0.0.1:3000',
    browserName: 'chromium',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  // These are viewport profiles, not a claim of three-browser qualification.
  projects: [
    { name: 'desktop', use: { viewport: { width: 1440, height: 1000 } } },
    { name: 'tablet', use: { viewport: { width: 820, height: 1180 } } },
    { name: 'mobile', use: { viewport: { width: 390, height: 844 } } },
  ],
});
