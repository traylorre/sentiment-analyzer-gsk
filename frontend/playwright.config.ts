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
  // Only start local servers when testing locally (not against deployed environment)
  // For remote testing (CI), the frontend is already deployed with API configured
  ...(isRemote
    ? {}
    : {
        // When webServer is an array, baseURL must be explicitly set (already done above)
        webServer: [
          {
            // Backend API server with mock DynamoDB
            // Provides ticker search, session auth, and other API endpoints
            // Uses the project's Python venv for dependencies
            command: 'cd .. && .venv/bin/python scripts/run-local-api.py',
            // Use API index endpoint for readiness check (returns 200 always)
            // /health returns 503 with mock DynamoDB, but API is still functional
            url: 'http://localhost:8000/api',
            reuseExistingServer: !process.env.CI,
            timeout: 30000,
            stdout: 'pipe',
            stderr: 'pipe',
          },
          {
            // Next.js frontend dev server
            command: 'npm run dev',
            url: 'http://localhost:3000',
            reuseExistingServer: !process.env.CI,
            timeout: 60000,
          },
        ],
      }),
});
