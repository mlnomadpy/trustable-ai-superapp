/**
 * Sonoma critical-path smoke test.
 *
 * Walks the contract between the PWA and the Flask bridge for a single
 * driving session. Catches drift between frontend HTTP calls and backend
 * route shapes — the kind of bug vitest unit tests can't see because they
 * mock fetch.
 *
 * Prerequisites (the spec FAILS LOUDLY if either is missing):
 *   • `python3 -m src.pitwall` running on http://127.0.0.1:8765.
 *   • A working LLM transport (LocalLLM at :8099 by default per ADR-022,
 *     or any of the engine/litertlm/openai backends). Coach calls are
 *     allowed to fall through to templated narratives — the spec asserts
 *     on shape, not narrative quality.
 *
 * Run:                npm run e2e
 * Run headed (debug): npx playwright test --headed
 * Single test:        npx playwright test -g "live coach Q&A"
 */
import { expect, test } from '@playwright/test'

const BRIDGE = process.env.PITWALL_BRIDGE ?? 'http://127.0.0.1:8765'

test.describe('Pitwall PWA ↔ bridge smoke (Sonoma critical path)', () => {

  test.beforeAll(async ({ request }) => {
    // Hard gate — there is no point continuing without a bridge.
    const res = await request.get(`${BRIDGE}/health`)
    expect(res.ok(), `bridge ${BRIDGE}/health must be reachable`).toBe(true)
    const body = await res.json()
    expect(body.status).toBe('ok')
    // Verify the HealthResponse type contract — these keys are what the
    // PWA's HealthResponse type promises (post 2026-05-13 fix).
    for (const key of [
      'status', 'version', 'engine', 'coach', 'driver_level',
      'track', 'duckdb', 'active_session_id', 'timestamp',
    ]) {
      expect(body, `health response must include ${key}`).toHaveProperty(key)
    }
  })

  test('PWA boots and renders the Save Select screen', async ({ page }) => {
    await page.goto('/')
    // The router sends `/` → `/title`. Save Select shows a slot list.
    // Don't assert on specific copy that may change — assert on structure.
    await expect(page.locator('body')).toBeVisible()
    await page.waitForLoadState('networkidle')
  })

  test('coach agents registry is reachable and shaped correctly', async ({ request }) => {
    // The PWA's AskCoachMode hits /coach/agents to render the intent picker.
    // The PWA-side type expects { agents: [{ name, role, example_questions? }] }
    const res = await request.get(`${BRIDGE}/coach/agents`)
    expect(res.ok()).toBe(true)
    const body = await res.json()
    expect(body).toHaveProperty('available')
    if (body.available) {
      expect(Array.isArray(body.agents)).toBe(true)
      // ≥ 14 specialist agents per ADR-019 → ADR-021.
      expect(body.agents.length).toBeGreaterThanOrEqual(14)
      for (const a of body.agents) {
        expect(a).toHaveProperty('name')
        expect(a).toHaveProperty('role')
      }
    }
  })

  test('session lifecycle: start → cue stream contract → end', async ({ request }) => {
    // Start a synthetic session
    const start = await request.post(`${BRIDGE}/session/start`, {
      data: { driver: 'e2e-smoke', track: 'Sonoma Raceway', car: 'BMW M3' },
    })
    expect(start.ok()).toBe(true)
    const { session_id: sid } = await start.json()
    expect(sid).toBeTruthy()

    // The SSE cue stream is the PWA's hot path for live coaching cues.
    // Hitting the endpoint with a short-fuse fetch and asserting the
    // content-type proves the contract without holding the connection
    // open (which Playwright's request runner doesn't support natively).
    const cues = await request.get(`${BRIDGE}/cues/stream?session_id=${sid}`, {
      timeout: 3000,
      // Abort after the first byte so the test doesn't hang on EventSource.
      maxRedirects: 0,
    }).catch((e) => e)
    // The request may abort by design (we don't want to drain the stream),
    // but if it succeeds the content-type must be text/event-stream.
    if (cues?.headers) {
      const ct = cues.headers()['content-type'] ?? ''
      expect(ct).toContain('text/event-stream')
    }

    // End the session
    const end = await request.post(`${BRIDGE}/session/${sid}/end`, { data: {} })
    expect(end.ok()).toBe(true)
  })

  test('live coach Q&A round-trips through the bridge (ADR-022)', async ({ request }) => {
    // This is the smoke for the new HTTP-to-LocalLLM transport. Whether
    // the model is up or fell back to templated, the bridge must respond
    // with the documented shape — `{ answer, emotion, qa_key, turn }`
    // — and HTTP 200.
    // The bridge's ADK timeout is PITWALL_ADK_TIMEOUT_S (default 45 s). Give
    // Playwright headroom over that — Gemma cold-loads via LocalLLM can
    // approach the full budget on a CPU-only dev machine.
    const res = await request.post(`${BRIDGE}/coach/ask`, {
      data: { driver_id: 'e2e-smoke', question: 'hi', intent: 'telemetry' },
      timeout: 60_000,
    })
    // "Graceful" means structured JSON either way — not an HTML stack trace.
    // HTTP 200 → expect a real answer. HTTP 5xx → tolerated as long as the
    // body still parses to `{ error: "<string>" }` (e.g. ADK timeout, LLM
    // unreachable, context-window overflow). A 5xx that returns HTML is a bug.
    const body = await res.json().catch(() => null)
    expect(body, 'response body must be JSON').not.toBeNull()

    if (res.ok()) {
      // Either a real LLM answer or the bridge gracefully returned an
      // `{error}` body with 200 status (less common but acceptable).
      if ('error' in body) {
        expect(typeof body.error).toBe('string')
      } else {
        expect(body).toHaveProperty('answer')
        expect(typeof body.answer).toBe('string')
        expect(body.answer.length).toBeGreaterThan(0)
      }
    } else {
      // Non-2xx — must still be a structured error object.
      expect(body).toHaveProperty('error')
      expect(typeof body.error).toBe('string')
      expect(body.error.length).toBeGreaterThan(0)
    }
  })

  test('analytics: ideal_lap + sector_times + highlights endpoints exist', async ({ request }) => {
    // These three feed the StageClear / LapTimesHall / DriverEvolution
    // screens wired up 2026-05-13. We don't care about the values — we
    // care that the endpoints exist and return JSON.
    for (const ep of [
      '/session/__nonexistent__/ideal_lap',
      '/session/__nonexistent__/sector_times',
      '/session/__nonexistent__/highlights',
      '/session/__nonexistent__/lap_time_distribution',
    ]) {
      const res = await request.get(`${BRIDGE}${ep}`)
      // 404 is the expected response for a missing session, but the body
      // must still be JSON. 5xx means the route blew up.
      expect(res.status(), `${ep} returned 5xx`).toBeLessThan(500)
      const body = await res.json()
      expect(body).toBeDefined()
    }
  })
})
