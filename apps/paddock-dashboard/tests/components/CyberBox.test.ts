import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import CyberBox from '@/shared/ui/core/CyberBox.vue'

describe('CyberBox.vue', () => {
  it('renders default slot content', () => {
    const wrapper = mount(CyberBox, {
      slots: {
        default: 'Box Content'
      }
    })
    
    expect(wrapper.text()).toContain('Box Content')
  })

  it('applies default classes', () => {
    const wrapper = mount(CyberBox)
    
    expect(wrapper.classes()).toContain('bg-charcoal')
    expect(wrapper.classes()).toContain('border-slate')
    expect(wrapper.classes()).not.toContain('interactive')
    expect(wrapper.classes()).not.toContain('selected')
  })

  it('applies explicit props', () => {
    const wrapper = mount(CyberBox, {
      props: {
        variant: 'glass',
        border: 'good',
        interactive: true,
        selected: true
      }
    })
    
    expect(wrapper.classes()).toContain('glass')
    expect(wrapper.classes()).toContain('border-good')
    expect(wrapper.classes()).toContain('interactive')
    expect(wrapper.classes()).toContain('selected')
  })
})
