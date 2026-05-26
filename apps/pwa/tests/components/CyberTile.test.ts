import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import CyberTile from '@/shared/ui/core/CyberTile.vue'
import CyberBox from '@/shared/ui/core/CyberBox.vue'

describe('CyberTile.vue', () => {
  it('renders default slot content', () => {
    const wrapper = mount(CyberTile, {
      slots: {
        default: '<div class="custom-content">Hello Tile</div>'
      }
    })
    
    expect(wrapper.find('.custom-content').exists()).toBe(true)
    expect(wrapper.text()).toContain('Hello Tile')
  })

  it('renders title and subText when no slot provided', () => {
    const wrapper = mount(CyberTile, {
      props: {
        title: 'Main Title',
        subText: 'Subtitle'
      }
    })
    
    expect(wrapper.text()).toContain('Main Title')
    expect(wrapper.text()).toContain('Subtitle')
  })

  it('emits click and hover events', async () => {
    const wrapper = mount(CyberTile)
    
    await wrapper.trigger('click')
    expect(wrapper.emitted()).toHaveProperty('click')
    
    await wrapper.trigger('mouseenter')
    expect(wrapper.emitted()).toHaveProperty('hover')
  })

  it('applies focused state classes and renders markers', () => {
    const wrapper = mount(CyberTile, {
      props: {
        focused: true,
        title: 'Focused Tile'
      }
    })
    
    // Check wrapper classes
    expect(wrapper.classes()).toContain('focused')
    
    // CyberBox props
    const cyberBox = wrapper.findComponent(CyberBox)
    expect(cyberBox.props('variant')).toBe('charcoal')
    expect(cyberBox.props('border')).toBe('good')
    
    // Focus marker
    expect(wrapper.find('.focus-marker').exists()).toBe(true)
    expect(wrapper.find('.focus-marker').text()).toBe('▼')
    
    // Cursor bounce marker
    expect(wrapper.find('.cursor-bounce').exists()).toBe(true)
    expect(wrapper.find('.cursor-bounce').text()).toBe('▶')
  })

  it('applies locked state classes and hides focus marker', () => {
    const wrapper = mount(CyberTile, {
      props: {
        locked: true,
        focused: true
      }
    })
    
    expect(wrapper.classes()).toContain('locked')
    // Focus marker should be hidden if locked
    expect(wrapper.find('.focus-marker').exists()).toBe(false)
  })

  it('renders kerb accent when showKerb and focused are true', () => {
    const wrapper = mount(CyberTile, {
      props: {
        showKerb: true,
        focused: true
      }
    })
    
    expect(wrapper.find('.tile-kerb').exists()).toBe(true)
  })

  it('does not render kerb accent when showKerb is true but not focused', () => {
    const wrapper = mount(CyberTile, {
      props: {
        showKerb: true,
        focused: false
      }
    })
    
    expect(wrapper.find('.tile-kerb').exists()).toBe(false)
  })
})
