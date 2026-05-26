import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import CyberListRow from '@/shared/ui/core/CyberListRow.vue'

describe('CyberListRow.vue', () => {
  it('renders title and detail', () => {
    const wrapper = mount(CyberListRow, {
      props: { title: 'Telemetry', detail: 'Connecting...' }
    })
    
    expect(wrapper.find('.row-title').text()).toBe('Telemetry')
    expect(wrapper.find('.row-detail').text()).toBe('Connecting...')
  })

  it('renders sublines', () => {
    const wrapper = mount(CyberListRow, {
      props: { 
        title: 'Network',
        subLines: ['IP: 192.168.1.1', 'Latency: 12ms']
      }
    })
    
    const subLines = wrapper.findAll('.row-sub')
    expect(subLines.length).toBe(2)
    expect(subLines[0].text()).toBe('IP: 192.168.1.1')
    expect(subLines[1].text()).toBe('Latency: 12ms')
  })

  it('renders OK status state correctly', () => {
    const wrapper = mount(CyberListRow, {
      props: { title: 'Status', statusState: 'ok', statusText: 'ALL GOOD' }
    })
    
    expect(wrapper.text()).toContain('ALL GOOD')
    expect(wrapper.text()).toContain('✓')
    expect(wrapper.find('.text-ui-good').exists()).toBe(true)
  })

  it('renders error status state correctly', () => {
    const wrapper = mount(CyberListRow, {
      props: { title: 'Status', statusState: 'error' }
    })
    
    expect(wrapper.text()).toContain('FAIL')
    expect(wrapper.text()).toContain('✗')
    expect(wrapper.find('.text-ui-bad').exists()).toBe(true)
  })

  it('renders checking status state correctly', () => {
    const wrapper = mount(CyberListRow, {
      props: { title: 'Status', statusState: 'checking' }
    })
    
    expect(wrapper.text()).toContain('▒▒')
    expect(wrapper.find('.animate-pulse').exists()).toBe(true)
  })

  it('applies pending class', () => {
    const wrapper = mount(CyberListRow, {
      props: { title: 'Status', statusState: 'pending' }
    })
    
    expect(wrapper.classes()).toContain('row-pending')
  })

  it('allows overriding icon with slot', () => {
    const wrapper = mount(CyberListRow, {
      props: { title: 'Status', statusState: 'error' },
      slots: {
        icon: '<span class="custom-icon">⚠️</span>'
      }
    })
    
    expect(wrapper.find('.custom-icon').exists()).toBe(true)
    expect(wrapper.text()).toContain('⚠️')
    expect(wrapper.text()).not.toContain('✗')
  })
})
