/**
 * Mock WebSocket for testing
 *
 * Usage in tests:
 *   import { MockWebSocket, createMockWebSocket } from '@/test/mocks/websocket'
 *
 *   beforeEach(() => {
 *     const mockWS = createMockWebSocket()
 *     global.WebSocket = vi.fn(() => mockWS) as any
 *   })
 *
 *   test('handles websocket message', () => {
 *     mockWS.simulateMessage({ type: 'player_state', data: {...} })
 *   })
 */

import { vi } from 'vitest'

// WebSocket constants (since they may not be available in test environment)
export const CONNECTING = 0
export const OPEN = 1
export const CLOSING = 2
export const CLOSED = 3

export class MockWebSocket {
  public url: string
  public readyState: number = CONNECTING
  public onopen: ((event: Event) => void) | null = null
  public onclose: ((event: CloseEvent) => void) | null = null
  public onerror: ((event: Event) => void) | null = null
  public onmessage: ((event: MessageEvent) => void) | null = null

  // Static constants
  static CONNECTING = CONNECTING
  static OPEN = OPEN
  static CLOSING = CLOSING
  static CLOSED = CLOSED

  private eventListeners: Map<string, Set<EventListenerOrEventListenerObject>> = new Map()

  constructor(url: string) {
    this.url = url
    // Simulate connection opening after a brief delay
    setTimeout(() => this.simulateOpen(), 0)
  }

  // Per WHATWG (https://websockets.spec.whatwg.org/#dom-websocket-send):
  // send() throws only while CONNECTING; while CLOSING/CLOSED it's a silent
  // no-op, and while OPEN it proceeds. This mock used to throw for any
  // non-OPEN state, which made CLOSING/CLOSED look like an error a real
  // WebSocket would never raise (#4491).
  send = vi.fn((_data: string) => {
    if (this.readyState === CONNECTING) {
      throw new Error("Failed to execute 'send' on 'WebSocket': Still in CONNECTING state.")
    }
    // CLOSING/CLOSED: no-op, matching the real WebSocket's silent discard.
  })

  close = vi.fn((code?: number, reason?: string) => {
    this.readyState = CLOSING
    setTimeout(() => this.simulateClose(code, reason), 0)
  })

  addEventListener = vi.fn((type: string, listener: EventListenerOrEventListenerObject) => {
    if (!this.eventListeners.has(type)) {
      this.eventListeners.set(type, new Set())
    }
    this.eventListeners.get(type)!.add(listener)
  })

  removeEventListener = vi.fn((type: string, listener: EventListenerOrEventListenerObject) => {
    const listeners = this.eventListeners.get(type)
    if (listeners) {
      listeners.delete(listener)
    }
  })

  dispatchEvent = vi.fn((event: Event) => {
    const listeners = this.eventListeners.get(event.type)
    if (listeners) {
      listeners.forEach((listener) => {
        if (typeof listener === 'function') {
          listener(event)
        } else {
          listener.handleEvent(event)
        }
      })
    }
    return true
  })

  // Test helper methods

  simulateOpen() {
    this.readyState = OPEN
    const event = new Event('open')
    if (this.onopen) this.onopen(event)
    this.dispatchEvent(event)
  }

  simulateClose(code = 1000, reason = 'Normal closure') {
    this.readyState = CLOSED
    const event = new CloseEvent('close', { code, reason })
    if (this.onclose) this.onclose(event)
    this.dispatchEvent(event)
  }

  simulateError() {
    const event = new Event('error')
    if (this.onerror) this.onerror(event)
    this.dispatchEvent(event)
  }

  simulateMessage(data: any) {
    if (this.readyState !== OPEN) {
      throw new Error('Cannot send message: WebSocket is not open')
    }
    const event = new MessageEvent('message', {
      data: JSON.stringify(data),
    })
    if (this.onmessage) this.onmessage(event)
    this.dispatchEvent(event)
  }
}

/**
 * Create a mock WebSocket instance
 */
export function createMockWebSocket(url = 'ws://localhost:8000/ws'): MockWebSocket {
  return new MockWebSocket(url)
}

/**
 * Setup global WebSocket mock
 */
export function mockWebSocket(): MockWebSocket {
  const mockWS = createMockWebSocket()
  global.WebSocket = vi.fn(() => mockWS) as any
  return mockWS
}

/**
 * Reset WebSocket mock
 */
export function resetWebSocketMock() {
  delete (global as any).WebSocket
}
