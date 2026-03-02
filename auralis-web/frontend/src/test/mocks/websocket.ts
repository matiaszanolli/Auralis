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

  send = vi.fn((_data: string) => {
    if (this.readyState !== OPEN) {
      throw new Error('WebSocket is not open')
    }
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

  scanProgress: (current: number, total: number, currentFile?: string) => ({
    type: 'scan_progress' as const,
    data: {
      current,
      total,
      percentage: total > 0 ? Math.round((current / total) * 100) : 0,
      current_file: currentFile,
    },
  }),

  connectionStatus: (connected: boolean) => ({
    type: 'connection_status',
    data: {
      connected,
      timestamp: new Date().toISOString(),
    },
  }),

  // Player state messages
  trackChanged: (action: 'next' | 'previous') => ({
    type: 'track_changed',
    data: { action },
  }),

  playbackStarted: () => ({
    type: 'playback_started',
    data: { state: 'playing' },
  }),

  playbackPaused: () => ({
    type: 'playback_paused',
    data: { state: 'paused' },
  }),

  playbackStopped: () => ({
    type: 'playback_stopped',
    data: { state: 'stopped' },
  }),

  positionChanged: (position: number) => ({
    type: 'position_changed',
    data: { position },
  }),

  volumeChanged: (volume: number) => ({
    type: 'volume_changed',
    data: { volume },
  }),

  queueUpdated: (action: string, queueSize: number, trackPath?: string, index?: number) => ({
    type: 'queue_updated',
    data: {
      action,
      queue_size: queueSize,
      ...(trackPath && { track_path: trackPath }),
      ...(index !== undefined && { index }),
    },
  }),

  // Enhancement messages
  enhancementSettingsChanged: (enabled: boolean, preset: string, intensity: number) => ({
    type: 'enhancement_settings_changed',
    data: { enabled, preset, intensity },
  }),

  // Library messages
  libraryUpdated: (action: string, trackCount?: number, albumCount?: number, artistCount?: number) => ({
    type: 'library_updated',
    data: {
      action,
      ...(trackCount && { track_count: trackCount }),
      ...(albumCount && { album_count: albumCount }),
      ...(artistCount && { artist_count: artistCount }),
    },
  }),

  // Playlist messages
  playlistCreated: (playlistId: number, name: string) => ({
    type: 'playlist_created',
    data: { playlist_id: playlistId, name },
  }),

  playlistUpdated: (playlistId: number, action: string) => ({
    type: 'playlist_updated',
    data: { playlist_id: playlistId, action },
  }),

  playlistDeleted: (playlistId: number) => ({
    type: 'playlist_deleted',
    data: { playlist_id: playlistId },
  }),

  // Favorite toggle
  favoriteToggled: (trackId: number, isFavorite: boolean) => ({
    type: 'favorite_toggled',
    data: { track_id: trackId, is_favorite: isFavorite },
  }),
}
