import { defineConfig, devices } from '@playwright/test';

// Support running against deployed environments (preprod/prod) or local dev server
// PREPROD_FRONTEND_URL is set in CI for testing deployed Amplify frontend
const baseURL = process.env.PREPROD_FRONTEND_URL || 'http://localhost:3000';
const isRemote = !!process.env.PREPROD_FRONTEND_URL;

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',
  use: {
    baseURL,
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'Mobile Chrome',
      use: { ...devices['Pixel 5'] },
    },
    {
      name: 'Mobile Safari',
      use: { ...devices['iPhone 13'] },
    },
    {
      name: 'Desktop Chrome',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  // Only start local dev server when testing locally (not against deployed environment)
  ...(isRemote
    ? {}
    : {
        webServer: {
          command: 'npm run dev',
          url: 'http://localhost:3000',
          reuseExistingServer: !process.env.CI,
        },
      }),
});
