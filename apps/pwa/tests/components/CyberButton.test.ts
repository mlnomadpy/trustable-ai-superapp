import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import CyberButton from '@/shared/ui/core/CyberButton.vue'

describe('CyberButton.vue', () => {
  it('renders default slot content', () => {
    const wrapper = mount(CyberButton, {
      slots: {
        default: 'Click Me'
      }
    })
    expect(wrapper.text()).toContain('Click Me')
  })

  it('emits click event when not disabled', async () => {
    const wrapper = mount(CyberButton)
    await wrapper.trigger('click')
    expect(wrapper.emitted()).toHaveProperty('click')
  })

  it('does not emit click event when disabled', async () => {
    const wrapper = mount(CyberButton, {
      props: { disabled: true }
    })
    await wrapper.trigger('click')
    expect(wrapper.emitted()).not.toHaveProperty('click')
  })

  it('applies correct variant and size classes', () => {
    const wrapper = mount(CyberButton, {
      props: {
        variant: 'secondary',
        size: 'lg',
        fluid: true
      }
    })
    expect(wrapper.classes()).toContain('secondary')
    expect(wrapper.classes()).toContain('lg')
    expect(wrapper.classes()).toContain('fluid')
  })

  it('renders subText correctly', () => {
    const wrapper = mount(CyberButton, {
      props: {
        subText: 'Secondary action'
      }
    })
    const subTextEl = wrapper.find('.sub-text')
    expect(subTextEl.exists()).toBe(true)
    expect(subTextEl.text()).toBe('Secondary action')
  })

  it('renders complex content without text wrapper when complex is true', () => {
    const wrapper = mount(CyberButton, {
      props: { complex: true },
      slots: {
        default: '<div class="custom-inner">Custom Content</div>'
      }
    })
    expect(wrapper.find('.complex-content').exists()).toBe(true)
    expect(wrapper.find('.text-content').exists()).toBe(false)
  })
})
