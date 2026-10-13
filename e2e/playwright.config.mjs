/** Test the built Compose application, never a separately spawned dev server. */
import { defineConfig } from '@playwright/test';

// Keep separate Playwright processes and evidence namespaces for behavioural
// regressions and screenshot-heavy visual reviews. Default local runs retain
// the existing combined artifact locations.
const suite = process.env.MATCHDESK_E2E_SUITE;
if (suite && !['functional', 'visual'].includes(suite)) {
  throw new Error('Unrecognised MatchDesk browser-evidence suite');
}
const artifactName = suite ? `browser-${suite}` : 'browser';

export default defineConfig({
  testDir: './specs',
  timeout: 30000,
  expect: { timeout: 7000 },
  forbidOnly: true,
  retries: 0, // Failures remain visible; reruns are separate recorded executions.
  workers: 1,
  outputDir: `../artifacts/integration/${artifactName}-results`,
  reporter: [
    ['list'],
    ['junit', { outputFile: `../artifacts/integration/${artifactName}-junit.xml` }],
    ['json', { outputFile: `../artifacts/integration/${artifactName}-results.json` }],
    ['html', { outputFolder: `../artifacts/integration/${artifactName}-report`, open: 'never' }],
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
