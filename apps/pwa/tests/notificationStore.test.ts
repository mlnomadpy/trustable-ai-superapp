import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useNotificationsStore } from '../src/shared/api/notificationStore'

describe('notificationStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('starts with empty items', () => {
    const store = useNotificationsStore()
    expect(store.items.length).toBe(0)
    expect(store.unreadCount).toBe(0)
  })

  it('marks specific notification as read', () => {
    const store = useNotificationsStore()
    store.add({ kind: 'medal-earned', title: 'MEDAL', subText: 'test', timestamp: 'now' })
    const id = store.items[0].id
    
    store.markRead(id)
    
    expect(store.items.find(i => i.id === id)?.isRead).toBe(true)
    expect(store.unreadCount).toBe(0)
  })

  it('marks all notifications as read', () => {
    const store = useNotificationsStore()
    store.add({ kind: 'medal-earned', title: 'A', subText: 'test', timestamp: 'now' })
    store.add({ kind: 'level-up', title: 'B', subText: 'test', timestamp: 'now' })
    
    store.markAllRead()
    
    expect(store.unreadCount).toBe(0)
    expect(store.items.every(i => i.isRead)).toBe(true)
  })

  it('adds new notification at the top', () => {
    const store = useNotificationsStore()
    
    store.add({
      kind: 'track-unlock',
      title: 'TEST NOTIFICATION',
      subText: 'This is a test',
      timestamp: 'just now'
    })
    
    expect(store.items.length).toBe(1)
    expect(store.items[0].title).toBe('TEST NOTIFICATION')
    expect(store.items[0].isRead).toBe(false)
    expect(store.items[0].id).toBeDefined()
    expect(store.unreadCount).toBe(1)
  })
})
