import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useSpriteStore } from '../src/entities/coach/model/spriteStore'

describe('spriteStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    document.head.innerHTML = ''
    
    // Default fetch mock for sprites
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        frames: {
          'frame1': { frame: { x: 0, y: 0, w: 32, h: 32 } },
          'frame2': { frame: { x: 32, y: 0, w: 32, h: 32 } }
        },
        animations: {
          'idle': { frames: ['frame1', 'frame2'], fps: 2, loop: true }
        }
      })
    }) as any
  })

  it('loads coach sheet via algorithmic path (no JSON fetch)', async () => {
    const store = useSpriteStore()
    await store.loadSheet('trod')

    // Coaches use algorithmic grid extraction — no JSON is fetched
    expect(global.fetch).not.toHaveBeenCalled()
    expect(store.loadedSheets.has('trod')).toBe(true)
  })

  it('loads non-coach sheet and injects CSS keyframes', async () => {
    const store = useSpriteStore()
    await store.loadSheet('frames')

    expect(global.fetch).toHaveBeenCalledWith('/sprites/ui/frames.json')
    expect(store.loadedSheets.has('frames')).toBe(true)
    
    // Check if style tag was injected
    const styleTag = document.getElementById('pitwall-sprite-keyframes')
    expect(styleTag).not.toBeNull()
    expect(styleTag?.textContent).toContain('@keyframes sprite-frames-idle')
  })

  it('cssFor returns algorithmic animation for coach sheets', () => {
    const store = useSpriteStore()
    store.loadedSheets.add('trod')
    
    const css = store.cssFor('trod', 'idle', { scale: 2, paused: true })
    
    // Coach sheets use the master grid system
    expect(css.backgroundSize).toBe('1000% 1000%')
    expect(css.animationPlayState).toBe('paused')
    expect(css.transform).toBe('scale(2)')
    expect(css.backgroundImage).toContain('/sprites/coaches/trod.png')
  })

  it('cssFor returns display none if non-coach sheet not loaded', () => {
    const store = useSpriteStore()
    const css = store.cssFor('frames', 'idle', { scale: 1, paused: false })
    
    expect(css.display).toBe('none')
    expect(global.fetch).toHaveBeenCalledWith('/sprites/ui/frames.json')
  })
})
