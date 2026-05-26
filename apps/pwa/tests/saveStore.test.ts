import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useSaveStore } from '../src/entities/save/model/saveStore'

// Need to import idb-keyval to check mock calls
import { get, set } from 'idb-keyval'

describe('saveStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('hydrates empty slots as null', async () => {
    const store = useSaveStore()
    // get is mocked to return undefined by default from our setup
    await store.hydrate()
    
    expect(store.slots).toEqual([null, null, null])
    expect(get).toHaveBeenCalledTimes(3)
  })

  it('hydrates with existing save data', async () => {
    // Setup mock idb store data
    const { _mockStore } = await import('idb-keyval') as any
    _mockStore.set('slot:2', { preferredCoach: 'drill', markers: [] })

    const store = useSaveStore()
    await store.hydrate()

    expect(store.slots[0]).toBeNull()
    expect(store.slots[1]).toEqual({ preferredCoach: 'drill', markers: [] })
    expect(store.slots[2]).toBeNull()
  })

  it('does not save if activeSlotId is null', async () => {
    const store = useSaveStore()
    store.activeSlotId = null
    await store.save()

    expect(set).not.toHaveBeenCalled()
  })

  it('saves active slot data to idb', async () => {
    const store = useSaveStore()
    store.slots[0] = { preferredCoach: 'bentley' } as any
    store.activeSlotId = 1
    
    await store.save()

    expect(set).toHaveBeenCalledWith('slot:1', { preferredCoach: 'bentley' })
  })
})
