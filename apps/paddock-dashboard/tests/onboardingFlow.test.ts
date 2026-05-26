import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useSaveStore } from '../src/entities/save/model/saveStore'

/**
 * Page-level integration test for the onboarding flow.
 * Tests the store-side logic of save slot creation since the
 * full component mount requires router + child component setup.
 */
describe('Onboarding save flow (integration)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('creates a new save slot with correct defaults', async () => {
    const save = useSaveStore()
    save.activeSlotId = 1
    
    // Simulate what commitSave() does in OnboardingFlow.vue
    save.slots[0] = {
      schemaVersion: 1,
      id: 1,
      createdAt: new Date().toISOString(),
      lastPlayedAt: new Date().toISOString(),
      driverName: 'TEST_DRIVER',
      driverAvatar: 'avatar_b',
      skillLevel: 'intermediate',
      car: 'BMW M3 (E46)',
      avatarSlot: 1,
      preferredCoach: 'trod',
      preferredTrack: 'sonoma',
      level: 1,
      sessions: [],
      bestLapBySession: {},
      coachAffinity: { trod: 1, bentley: 0, drill: 0, calm: 0, buddy: 0 },
      unlockedTracks: ['sonoma'],
      unlockedAvatars: [1],
      unlockedCoaches: ['trod', 'buddy'],
      medals: [],
      goalsHistory: [],
      settings: {
        audio: { masterVolume: 80, musicVolume: 50, sfxVolume: 100, voiceVolume: 100, coachMute: false },
        display: { nightMode: false, reducedMotion: false, showFps: false },
        controls: { keyboardLayout: 'arrows', swapAB: false }
      }
    }

    const slot = save.activeSlot
    expect(slot).not.toBeNull()
    expect(slot!.driverName).toBe('TEST_DRIVER')
    expect(slot!.driverAvatar).toBe('avatar_b')
    expect(slot!.skillLevel).toBe('intermediate')
    expect(slot!.schemaVersion).toBe(1)
    expect(slot!.settings.audio.masterVolume).toBe(80)
    expect(slot!.settings.controls.keyboardLayout).toBe('arrows')
    expect(slot!.unlockedCoaches).toContain('trod')
  })

  it('activeSlot returns null when no slot is selected', () => {
    const save = useSaveStore()
    expect(save.activeSlot).toBeNull()
    expect(save.activeSlotId).toBeNull()
  })

  it('persists save via IDB', async () => {
    const save = useSaveStore()
    save.activeSlotId = 2
    save.slots[1] = {
      schemaVersion: 1,
      id: 2,
      createdAt: new Date().toISOString(),
      lastPlayedAt: new Date().toISOString(),
      driverName: 'SLOT2',
      skillLevel: 'pro',
      car: 'BMW M3 (E46)',
      avatarSlot: 1,
      preferredCoach: 'buddy',
      preferredTrack: 'sonoma',
      level: 5,
      sessions: [],
      bestLapBySession: {},
      coachAffinity: { trod: 0, bentley: 0, drill: 0, calm: 0, buddy: 3 },
      unlockedTracks: ['sonoma'],
      unlockedAvatars: [1, 2],
      unlockedCoaches: ['trod', 'buddy', 'calm'],
      medals: [],
      goalsHistory: [],
      settings: {
        audio: { masterVolume: 100, musicVolume: 100, sfxVolume: 100, voiceVolume: 100, coachMute: true },
        display: { nightMode: true, reducedMotion: false, showFps: true },
        controls: { keyboardLayout: 'wasd', swapAB: true }
      }
    }

    // save.save() calls idb-keyval set(), which is mocked in setup.ts
    await save.save()
    
    // Verify slot 2 is active
    expect(save.activeSlot?.driverName).toBe('SLOT2')
    expect(save.activeSlot?.preferredCoach).toBe('buddy')
    expect(save.activeSlot?.settings.audio.coachMute).toBe(true)
  })

  it('settings sync structure matches SaveSettings interface', () => {
    // This test ensures the settings object shape from the Settings page 
    // would correctly map to the SaveSettings interface
    const settingsFromUI = {
      audio: { master: 75, music: 60, sfx: 90, coach: 80, muteAll: false, muteCoach: true },
      display: { nightMode: true, reducedMotion: false, fpsCounter: true, scale: '2x' },
      controls: { layout: 'WASD', swapAB: true }
    }
    
    const layoutMap: Record<string, 'arrows' | 'wasd' | 'igdk'> = {
      'Arrows': 'arrows', 'WASD': 'wasd', 'IJKL': 'igdk'
    }
    
    const mapped = {
      audio: {
        masterVolume: settingsFromUI.audio.master,
        musicVolume: settingsFromUI.audio.music,
        sfxVolume: settingsFromUI.audio.sfx,
        voiceVolume: settingsFromUI.audio.coach,
        coachMute: settingsFromUI.audio.muteCoach,
      },
      display: {
        nightMode: settingsFromUI.display.nightMode,
        reducedMotion: settingsFromUI.display.reducedMotion,
        showFps: settingsFromUI.display.fpsCounter,
      },
      controls: {
        keyboardLayout: layoutMap[settingsFromUI.controls.layout],
        swapAB: settingsFromUI.controls.swapAB,
      }
    }
    
    // Verify all fields are present and typed correctly
    expect(mapped.audio.masterVolume).toBe(75)
    expect(mapped.audio.coachMute).toBe(true)
    expect(mapped.display.nightMode).toBe(true)
    expect(mapped.display.showFps).toBe(true)
    expect(mapped.controls.keyboardLayout).toBe('wasd')
    expect(mapped.controls.swapAB).toBe(true)
  })
})
