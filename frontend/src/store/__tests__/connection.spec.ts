import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useConnectionStore } from '../connection'

describe('useConnectionStore', () => {
  beforeEach(() => { setActivePinia(createPinia()) })

  it('starts disconnected', () => {
    const store = useConnectionStore()
    expect(store.status).toBe('disconnected')
    expect(store.isConnected).toBe(false)
  })

  it('setConnected updates status and protocol', () => {
    const store = useConnectionStore()
    store.setConnected(3)
    expect(store.status).toBe('connected')
    expect(store.protocolVersion).toBe(3)
    expect(store.isConnected).toBe(true)
  })

  it('addWarning caps at 20', () => {
    const store = useConnectionStore()
    for (let i = 0; i < 25; i++) store.addWarning(`warn ${i}`)
    expect(store.warnings.length).toBe(20)
  })
})
