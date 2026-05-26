import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAudioStore } from '../src/features/audio-playback/model/audioStore'
import { Howl } from 'howler'

describe('audioStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('plays sfx and caches Howl instance', () => {
    const store = useAudioStore()
    store.playSfx('cursor_move')

    expect(store.sfx.has('cursor_move')).toBe(true)
    const howlMock = store.sfx.get('cursor_move')!
    expect(howlMock.play).toHaveBeenCalled()
  })

  it('plays music, fades others, and caches instance', () => {
    const store = useAudioStore()
    
    // Play first track
    store.playMusic('title_loop')
    expect(store.music.has('title_loop')).toBe(true)
    
    // Play second track, should fade first
    store.playMusic('garage_loop')
    
    const track1 = store.music.get('title_loop')!
    const track2 = store.music.get('garage_loop')!
    
    expect(track1.fade).toHaveBeenCalled()
    expect(track2.play).toHaveBeenCalled()
    expect(track2.fade).toHaveBeenCalled()
  })

  it('ducks music when voice is played', () => {
    const store = useAudioStore()
    store.playMusic('title_loop')
    
    // Mock that music is playing
    const musicMock = store.music.get('title_loop')!
    vi.mocked(musicMock.playing).mockReturnValue(true)

    store.playVoice('trod', 'welcome', 1000)

    expect(musicMock.fade).toHaveBeenCalledWith(undefined, 0.05, 200)
    expect(store.ttsDucked).toBe(true)
  })
})
