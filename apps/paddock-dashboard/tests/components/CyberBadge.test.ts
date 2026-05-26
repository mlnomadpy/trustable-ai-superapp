import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import CyberBadge from '@/shared/ui/core/CyberBadge.vue'

describe('CyberBadge.vue', () => {
  it('renders default slot content', () => {
    const wrapper = mount(CyberBadge, {
      slots: {
        default: 'NEW ITEM'
      }
    })
    expect(wrapper.text()).toContain('NEW ITEM')
  })

  it('applies default info variant', () => {
    const wrapper = mount(CyberBadge)
    expect(wrapper.classes()).toContain('info')
  })

  it('applies specific variants', () => {
    const wrapper = mount(CyberBadge, {
      props: { variant: 'good' }
    })
    expect(wrapper.classes()).toContain('good')
    expect(wrapper.classes()).not.toContain('info')
  })

  it('applies pulse animation class when pulse prop is true', () => {
    const wrapper = mount(CyberBadge, {
      props: { pulse: true }
    })
    expect(wrapper.classes()).toContain('animate-pulse')
  })

  it('does not apply pulse animation by default', () => {
    const wrapper = mount(CyberBadge)
    expect(wrapper.classes()).not.toContain('animate-pulse')
  })
})
