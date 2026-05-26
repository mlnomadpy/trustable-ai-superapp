import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import CyberPanel from '@/shared/ui/core/CyberPanel.vue'

describe('CyberPanel.vue', () => {
  it('renders default slot content', () => {
    const wrapper = mount(CyberPanel, {
      slots: {
        default: '<div class="test-content">Hello Panel</div>'
      }
    })
    
    expect(wrapper.find('.test-content').exists()).toBe(true)
    expect(wrapper.text()).toContain('Hello Panel')
  })

  it('applies default variants', () => {
    const wrapper = mount(CyberPanel)
    
    expect(wrapper.classes()).toContain('solid')
    expect(wrapper.classes()).toContain('border-primary')
    expect(wrapper.classes()).not.toContain('interactive')
  })

  it('applies specific variants', () => {
    const wrapper = mount(CyberPanel, {
      props: {
        variant: 'glass',
        border: 'warn',
        interactive: true
      }
    })
    
    expect(wrapper.classes()).toContain('glass')
    expect(wrapper.classes()).toContain('border-warn')
    expect(wrapper.classes()).toContain('interactive')
  })
})
