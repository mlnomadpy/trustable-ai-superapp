import { defineConfig, devices } from '@playwright/test'

/**
 * Playwright smoke configuration for the Pitwall PWA.
 *
 * The smoke spec at `tests/e2e/sonoma-smoke.spec.ts` walks the critical
 * Sonoma-day flow: PWA boot → session start → cue stream open → ADK ask →
 * debrief. It needs:
 *
 *   1. The Python bridge running on http://127.0.0.1:8765 (start with
 *      `python3 -m src.pitwall` from the repo root).
 *   2. LocalLLM (or any OpenAI-compat server) reachable per ADR-022, or
 *      the bridge configured to use the templated fallback. The smoke
 *      tolerates an unhealthy LLM — it asserts on the *contract*, not the
 *      narrative quality.
 *
 * One-time install:  `npx playwright install chromium`
 * Run smoke:         `npm run e2e`
 */
export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: false,           // one bridge process; serialise.
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: process.env.CI ? 'github' : 'list',
  timeout: 60_000,                // ADK + LocalLLM cold start can take 10–15 s.
  expect: { timeout: 10_000 },

  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://127.0.0.1:5173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },

  // Boot the Vite dev server automatically when the smoke runs.
  // Disable with E2E_NO_WEBSERVER=1 if you're already serving the PWA
  // (e.g. from a built dist via `npm run preview`).
  webServer: process.env.E2E_NO_WEBSERVER
    ? undefined
    : {
        command: 'npm run dev',
        url: 'http://127.0.0.1:5173',
        reuseExistingServer: !process.env.CI,
        timeout: 60_000,
      },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
})
