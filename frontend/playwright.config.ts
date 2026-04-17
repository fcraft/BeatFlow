import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  retries: 0,
  reporter: 'list',
  use: {
    baseURL: 'https://localhost:3080',
    headless: true,
    actionTimeout: 5_000,
    ignoreHTTPSErrors: true,
  },
  projects: [
    {
      name: 'desktop-chromium',
      use: {
        browserName: 'chromium',
        viewport: { width: 1280, height: 900 },
      },
    },
    {
      name: 'mobile-iphone-se',
      use: {
        ...devices['iPhone SE'],
        browserName: 'chromium',
      },
    },
    {
      name: 'mobile-iphone-14',
      use: {
        ...devices['iPhone 14'],
        browserName: 'chromium',
      },
    },
    {
      name: 'tablet-ipad',
      use: {
        ...devices['iPad (gen 7)'],
        browserName: 'chromium',
      },
    },
  ],
})
