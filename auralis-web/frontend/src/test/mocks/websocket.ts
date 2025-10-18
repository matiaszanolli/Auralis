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

export class MockWebSocket {
  public url: string
  public readyState: number = WebSocket.CONNECTING
  public onopen: ((event: Event) => void) | null = null
  public onclose: ((event: CloseEvent) => void) | null = null
  public onerror: ((event: Event) => void) | null = null
  public onmessage: ((event: MessageEvent) => void) | null = null

  private eventListeners: Map<string, Set<EventListenerOrEventListenerObject>> = new Map()

  constructor(url: string) {
    this.url = url
    // Simulate connection opening after a brief delay
    setTimeout(() => this.simulateOpen(), 0)
  }

  send = vi.fn((data: string) => {
    if (this.readyState !== WebSocket.OPEN) {
      throw new Error('WebSocket is not open')
    }
  })

  close = vi.fn((code?: number, reason?: string) => {
    this.readyState = WebSocket.CLOSING
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
    this.readyState = WebSocket.OPEN
    const event = new Event('open')
    if (this.onopen) this.onopen(event)
    this.dispatchEvent(event)
  }

  simulateClose(code = 1000, reason = 'Normal closure') {
    this.readyState = WebSocket.CLOSED
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
    if (this.readyState !== WebSocket.OPEN) {
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

// ============================================================================
// Mock WebSocket Messages
// ============================================================================

export const mockWSMessages = {
  playerState: (data: any) => ({
    type: 'player_state',
    data,
  }),

  processingProgress: (progress: number, message: string) => ({
    type: 'processing_progress',
    data: {
      progress,
      message,
      timestamp: new Date().toISOString(),
    },
  }),

  processingComplete: (jobId: string, outputFile: string) => ({
    type: 'processing_complete',
    data: {
      job_id: jobId,
      output_file: outputFile,
      timestamp: new Date().toISOString(),
    },
  }),

  processingError: (jobId: string, error: string) => ({
    type: 'processing_error',
    data: {
      job_id: jobId,
      error,
      timestamp: new Date().toISOString(),
    },
  }),

  libraryUpdate: (action: string, data: any) => ({
    type: 'library_update',
    data: {
      action,
      ...data,
    },
  }),

  scanProgress: (filesScanned: number, filesFound: number, currentFile: string) => ({
    type: 'scan_progress',
    data: {
      files_scanned: filesScanned,
      files_found: filesFound,
      current_file: currentFile,
      timestamp: new Date().toISOString(),
    },
  }),

  connectionStatus: (connected: boolean) => ({
    type: 'connection_status',
    data: {
      connected,
      timestamp: new Date().toISOString(),
    },
  }),
}
