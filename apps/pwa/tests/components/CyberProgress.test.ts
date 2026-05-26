import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import CyberProgress from '@/shared/ui/core/CyberProgress.vue'

describe('CyberProgress.vue', () => {
  it('calculates correct width percentage', () => {
    const wrapper = mount(CyberProgress, {
      props: { value: 50, max: 100 }
    })
    const fill = wrapper.find('.cyber-progress-fill')
    expect(fill.attributes('style')).toContain('width: 50%')
  })

  it('clamps width percentage to 100%', () => {
    const wrapper = mount(CyberProgress, {
      props: { value: 150, max: 100 }
    })
    const fill = wrapper.find('.cyber-progress-fill')
    expect(fill.attributes('style')).toContain('width: 100%')
  })

  it('clamps width percentage to 0%', () => {
    const wrapper = mount(CyberProgress, {
      props: { value: -10, max: 100 }
    })
    const fill = wrapper.find('.cyber-progress-fill')
    expect(fill.attributes('style')).toContain('width: 0%')
  })

  it('applies thickness class', () => {
    const wrapper = mount(CyberProgress, {
      props: { value: 50, thickness: 'lg' }
    })
    expect(wrapper.classes()).toContain('thickness-lg')
  })

  it('applies variant class', () => {
    const wrapper = mount(CyberProgress, {
      props: { value: 50, variant: 'bad' }
    })
    const fill = wrapper.find('.cyber-progress-fill')
    expect(fill.classes()).toContain('fill-bad')
  })

  it('adds animation class when animated and > 0', () => {
    const wrapper = mount(CyberProgress, {
      props: { value: 50, animated: true }
    })
    const fill = wrapper.find('.cyber-progress-fill')
    expect(fill.classes()).toContain('animate-pulse-slow')
  })

  it('removes animation class when value is 0', () => {
    const wrapper = mount(CyberProgress, {
      props: { value: 0, animated: true }
    })
    const fill = wrapper.find('.cyber-progress-fill')
    expect(fill.classes()).not.toContain('animate-pulse-slow')
  })
})
