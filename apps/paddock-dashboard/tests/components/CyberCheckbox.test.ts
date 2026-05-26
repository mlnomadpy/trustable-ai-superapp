import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import CyberCheckbox from '@/shared/ui/core/CyberCheckbox.vue'

describe('CyberCheckbox.vue', () => {
  it('renders unchecked state with label', () => {
    const wrapper = mount(CyberCheckbox, {
      props: { checked: false, label: 'MUTE ALL', focused: false }
    })

    expect(wrapper.text()).toContain('MUTE ALL')
    // Unchecked: no SVG check icon present, aria-checked is false
    expect(wrapper.find('svg.check-icon').exists()).toBe(false)
    expect(wrapper.attributes('aria-checked')).toBe('false')
  })

  it('renders checked state correctly', () => {
    const wrapper = mount(CyberCheckbox, {
      props: { checked: true, label: 'NIGHT MODE', focused: false }
    })

    // Checked: SVG check icon is rendered, aria-checked is true
    expect(wrapper.find('svg.check-icon').exists()).toBe(true)
    expect(wrapper.attributes('aria-checked')).toBe('true')
  })

  it('shows cursor arrow when focused', () => {
    const wrapper = mount(CyberCheckbox, {
      props: { checked: false, label: 'TEST', focused: true }
    })

    // The focus marker is always in DOM; focused state makes it fully opaque.
    const marker = wrapper.find('.focus-marker')
    expect(marker.exists()).toBe(true)
    expect(marker.text()).toBe('▶')
    expect(marker.classes()).toContain('opacity-100')
    expect(marker.classes()).not.toContain('opacity-0')
  })

  it('hides cursor arrow when not focused', () => {
    const wrapper = mount(CyberCheckbox, {
      props: { checked: false, label: 'TEST', focused: false }
    })

    // Marker stays in DOM (animated via opacity), but is opacity-0 when unfocused.
    const marker = wrapper.find('.focus-marker')
    expect(marker.exists()).toBe(true)
    expect(marker.classes()).toContain('opacity-0')
    expect(marker.classes()).not.toContain('opacity-100')
  })

  it('renders sub-label when provided', () => {
    const wrapper = mount(CyberCheckbox, {
      props: { checked: false, label: 'MUTE', focused: false, subLabel: '(silence mode)' }
    })

    expect(wrapper.text()).toContain('(silence mode)')
  })
})
