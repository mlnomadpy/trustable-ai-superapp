import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import SessionStartPicker from '@/widgets/session-start/SessionStartPicker.vue'

// Bridge mock — controlled per-test by reassigning the implementation of each
// stubbed verb. Default get() handles both /sessions and /session/replay/status
// to keep onMounted happy without per-test setup.
const sampleSessions = [
  {
    session_id: 'track-sonoma-2026-05-23-1',
    driver: 'Taha',
    driver_level: 'intermediate',
    track: 'sonoma',
    car: 'gt3',
    started_at: '2026-05-23T10:00:00',
    ended_at: null,
    note: '',
    lap_count: 5,
    best_lap_s: 92.345,
  },
  {
    session_id: 'track-sonoma-2026-05-22-1',
    driver: 'Taha',
    driver_level: 'intermediate',
    track: 'sonoma',
    car: 'gt3',
    started_at: '2026-05-22T10:00:00',
    ended_at: '2026-05-22T10:30:00',
    note: '',
    lap_count: 3,
    best_lap_s: 95.0,
  },
]

const { bridgeMock } = vi.hoisted(() => ({
  bridgeMock: {
    get: vi.fn(),
    post: vi.fn(),
  },
}))

vi.mock('@/shared/api/bridge', () => ({
  bridge: bridgeMock,
}))

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/garage/pit-stall', component: { template: '<div />' } },
    ],
  })
}

async function mountPicker() {
  const router = makeRouter()
  await router.push('/')
  await router.isReady()
  const wrapper = mount(SessionStartPicker, {
    global: {
      plugins: [router],
    },
  })
  // Allow onMounted fetchSessions + pollStatus to settle.
  await flushPromises()
  return { wrapper, router }
}

function defaultGet(endpoint: string) {
  if (endpoint.startsWith('/sessions')) {
    return Promise.resolve({ sessions: sampleSessions })
  }
  if (endpoint === '/session/replay/status') {
    return Promise.resolve({ running: false })
  }
  return Promise.reject(new Error(`unexpected GET ${endpoint}`))
}

describe('SessionStartPicker.vue', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    bridgeMock.get.mockReset()
    bridgeMock.post.mockReset()
    bridgeMock.get.mockImplementation(defaultGet)
    bridgeMock.post.mockResolvedValue({})
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('fetches /sessions on mount and renders them in a <select>', async () => {
    const { wrapper } = await mountPicker()

    expect(bridgeMock.get).toHaveBeenCalledWith('/sessions?limit=50')

    const select = wrapper.find('select')
    expect(select.exists()).toBe(true)
    const options = select.findAll('option')
    expect(options.length).toBe(sampleSessions.length)
    expect(options[0].text()).toContain('track-sonoma-2026-05-23-1')
    expect(options[1].text()).toContain('track-sonoma-2026-05-22-1')
  })

  it('polls /session/replay/status every 2 seconds', async () => {
    await mountPicker()

    const statusCallsAtMount = bridgeMock.get.mock.calls.filter(
      (c) => c[0] === '/session/replay/status'
    ).length
    // onMounted fires one status call immediately.
    expect(statusCallsAtMount).toBe(1)

    // Advance two intervals = +2 polls.
    await vi.advanceTimersByTimeAsync(2_000)
    await vi.advanceTimersByTimeAsync(2_000)

    const statusCallsAfter = bridgeMock.get.mock.calls.filter(
      (c) => c[0] === '/session/replay/status'
    ).length
    expect(statusCallsAfter).toBe(statusCallsAtMount + 2)
  })

  it('clicking START posts to /session/replay/start with form values', async () => {
    const { wrapper } = await mountPicker()

    // Default selection should be the preferred session id.
    const select = wrapper.find('select')
    expect((select.element as HTMLSelectElement).value).toBe(
      'track-sonoma-2026-05-23-1'
    )

    // Click START — the first <button> in the idle layout.
    const startBtn = wrapper.find('button')
    await startBtn.trigger('click')
    await flushPromises()

    expect(bridgeMock.post).toHaveBeenCalledWith('/session/replay/start', {
      source_session_id: 'track-sonoma-2026-05-23-1',
      speed: 1,
      loop: false,
    })
  })

  it('switches START button to STOP when status returns running:true', async () => {
    bridgeMock.get.mockImplementation((endpoint: string) => {
      if (endpoint.startsWith('/sessions')) {
        return Promise.resolve({ sessions: sampleSessions })
      }
      if (endpoint === '/session/replay/status') {
        return Promise.resolve({
          running: true,
          source_session_id: 'track-sonoma-2026-05-23-1',
          speed: 1,
          loop: false,
          frame_idx: 100,
          total_frames: 1000,
          elapsed_s: 10,
        })
      }
      return Promise.reject(new Error(`unexpected GET ${endpoint}`))
    })

    const { wrapper } = await mountPicker()

    const text = wrapper.text()
    expect(text).toContain('STOP SESSION')
    expect(text).not.toContain('START SIMULATED SESSION')
  })

  it('clicking STOP posts to /session/replay/stop', async () => {
    bridgeMock.get.mockImplementation((endpoint: string) => {
      if (endpoint.startsWith('/sessions')) {
        return Promise.resolve({ sessions: sampleSessions })
      }
      if (endpoint === '/session/replay/status') {
        return Promise.resolve({
          running: true,
          source_session_id: 'track-sonoma-2026-05-23-1',
          frame_idx: 1,
          total_frames: 100,
        })
      }
      return Promise.reject(new Error(`unexpected GET ${endpoint}`))
    })

    const { wrapper } = await mountPicker()

    // STOP SESSION button is the first action button in the running layout.
    const buttons = wrapper.findAll('button')
    const stopBtn = buttons.find((b) => b.text().includes('STOP SESSION'))
    expect(stopBtn).toBeTruthy()
    await stopBtn!.trigger('click')
    await flushPromises()

    expect(bridgeMock.post).toHaveBeenCalledWith('/session/replay/stop', {})
  })

  it('shows "Replay already running" toast on 409 start response', async () => {
    bridgeMock.post.mockRejectedValueOnce(
      new Error('Bridge POST /session/replay/start failed: 409 Conflict')
    )

    const { wrapper } = await mountPicker()
    const startBtn = wrapper.find('button')
    await startBtn.trigger('click')
    await flushPromises()

    const text = wrapper.text()
    expect(text.toLowerCase()).toContain('already running')
  })

  it('shows "no telemetry rows" toast on 404 start response', async () => {
    bridgeMock.post.mockRejectedValueOnce(
      new Error('Bridge POST /session/replay/start failed: 404 Not Found')
    )

    const { wrapper } = await mountPicker()
    const startBtn = wrapper.find('button')
    await startBtn.trigger('click')
    await flushPromises()

    const text = wrapper.text()
    // Component message: "Selected session has no telemetry rows."
    expect(text.toLowerCase()).toContain('no telemetry rows')
  })
})
