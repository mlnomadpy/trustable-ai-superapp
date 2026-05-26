import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import Sprite from '@/entities/coach/Sprite.vue'
import { setActivePinia, createPinia } from 'pinia'
import { useSpriteStore } from '@/entities/coach/model/spriteStore'

describe('Sprite.vue', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    document.head.innerHTML = ''
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({})
    }) as any
  })

  it('renders correctly and sets initial class names', () => {
    const wrapper = mount(Sprite, {
      props: {
        sheet: 'trod',
        animation: 'idle'
      }
    })
    
    expect(wrapper.classes()).toContain('sprite')
    expect(wrapper.classes()).toContain('sprite-trod')
    expect(wrapper.classes()).toContain('sprite-idle')
  })

  it('gets css from store based on props', () => {
    const store = useSpriteStore()
    vi.spyOn(store, 'cssFor').mockReturnValue({ display: 'inline-block', transform: 'scale(2)' })
    
    const wrapper = mount(Sprite, {
      props: { sheet: 'trod', animation: 'idle', scale: 2, paused: true }
    })
    
    expect(store.cssFor).toHaveBeenCalledWith('trod', 'idle', { scale: 2, paused: true })
    const styleAttr = wrapper.attributes('style') || ''
    expect(styleAttr).toContain('display: inline-block')
    expect(styleAttr).toContain('transform: scale(2)')
  })

  it('emits animationend event when animation completes', async () => {
    const wrapper = mount(Sprite, {
      props: { sheet: 'trod', animation: 'idle' }
    })
    
    await wrapper.trigger('animationend')
    
    expect(wrapper.emitted()).toHaveProperty('animationend')
  })
})
