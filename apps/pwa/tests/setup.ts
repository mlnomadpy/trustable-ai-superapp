import { vi } from 'vitest'

// Mock API config
vi.mock('@/shared/config/api', () => ({
  API_BASE: 'http://127.0.0.1:8765'
}))

// Mock idb-keyval
vi.mock('idb-keyval', () => {
  const store = new Map()
  return {
    get: vi.fn(async (key) => store.get(key)),
    set: vi.fn(async (key, val) => store.set(key, val)),
    del: vi.fn(async (key) => store.delete(key)),
    clear: vi.fn(async () => store.clear()),
    _mockStore: store // for test inspection
  }
})

// Mock howler
vi.mock('howler', () => {
  return {
    Howl: class {
      play = vi.fn()
      pause = vi.fn()
      stop = vi.fn()
      mute = vi.fn()
      volume = vi.fn()
      unload = vi.fn()
      on = vi.fn()
      fade = vi.fn()
      playing = vi.fn()
      duration = vi.fn()
      once = vi.fn()
    },
    Howler: {
      mute: vi.fn(),
      volume: vi.fn()
    }
  }
})

// Mock duckdb-wasm
vi.mock('@duckdb/duckdb-wasm', () => {
  return {
    ConsoleLogger: vi.fn(),
    createWorker: vi.fn(),
    AsyncDuckDB: class {
      instantiate = vi.fn()
      connect = vi.fn().mockImplementation(() => ({
        query: vi.fn().mockResolvedValue({
          toArray: () => [{ distance_m: 100, speed_kmh: 200 }]
        }),
        close: vi.fn()
      }))
      registerFileBuffer = vi.fn()
    },
    getJsDelivrBundles: vi.fn().mockReturnValue({ mvp: { mainModule: '', mainWorker: '' } }),
    selectBundle: vi.fn().mockResolvedValue({ mainWorker: '', mainModule: '', pthreadWorker: '' })
  }
})

// Mock EventSource
global.EventSource = class {
  close = vi.fn()
  addEventListener = vi.fn()
  removeEventListener = vi.fn()
  onmessage = vi.fn()
  onerror = vi.fn()
} as any

// Mock Worker
global.Worker = class {
  postMessage = vi.fn()
  terminate = vi.fn()
  addEventListener = vi.fn()
  removeEventListener = vi.fn()
} as any

// Mock fetch
global.fetch = vi.fn().mockResolvedValue({
  ok: true,
  json: async () => ({}),
  text: async () => '',
  arrayBuffer: async () => new ArrayBuffer(0)
}) as any

// Mock OPFS (navigator.storage)
Object.defineProperty(global, 'navigator', {
  value: {
    storage: {
      getDirectory: vi.fn().mockResolvedValue({
        getDirectoryHandle: vi.fn().mockResolvedValue({
          getFileHandle: vi.fn().mockResolvedValue({
            createWritable: vi.fn().mockResolvedValue({
              write: vi.fn(),
              close: vi.fn()
            })
          })
        })
      })
    }
  },
  writable: true
})
