/**
 * Mock API responses for testing
 *
 * Usage in tests:
 *   import { mockFetch, mockApiEndpoint } from '@/test/mocks/api'
 *
 *   beforeEach(() => {
 *     mockFetch()
 *     mockApiEndpoint('/api/tracks', mockTracks)
 *   })
 */

import { vi } from 'vitest'

/**
 * Mock fetch globally
 */
export function mockFetch() {
  global.fetch = vi.fn()
}

/**
 * Reset fetch mock
 */
export function resetFetchMock() {
  vi.mocked(fetch).mockReset()
}

/**
 * Mock a specific API endpoint with a response
 */
export function mockApiEndpoint(
  endpoint: string,
  data: any,
  options: { status?: number; delay?: number } = {}
) {
  const { status = 200, delay = 0 } = options

  vi.mocked(fetch).mockImplementation((url) => {
    if (typeof url === 'string' && url.includes(endpoint)) {
      return Promise.resolve({
        ok: status >= 200 && status < 300,
        status,
        json: async () => {
          if (delay > 0) {
            await new Promise((resolve) => setTimeout(resolve, delay))
          }
          return data
        },
        text: async () => JSON.stringify(data),
        headers: new Headers({ 'Content-Type': 'application/json' }),
      } as Response)
    }
    return Promise.reject(new Error(`Unhandled fetch to ${url}`))
  })
}

/**
 * Mock API error response
 */
export function mockApiError(endpoint: string, error: string, status = 500) {
  vi.mocked(fetch).mockImplementation((url) => {
    if (typeof url === 'string' && url.includes(endpoint)) {
      return Promise.resolve({
        ok: false,
        status,
        json: async () => ({ error }),
        text: async () => JSON.stringify({ error }),
        headers: new Headers({ 'Content-Type': 'application/json' }),
      } as Response)
    }
    return Promise.reject(new Error(`Unhandled fetch to ${url}`))
  })
}

// ============================================================================
// Mock Data
// ============================================================================

export const mockTrack = {
  id: 1,
  title: 'Test Track',
  artist: 'Test Artist',
  album: 'Test Album',
  duration: 180,
  file_path: '/path/to/track.mp3',
  genre: 'Electronic',
  year: 2024,
}

export const mockTracks = [
  mockTrack,
  {
    id: 2,
    title: 'Another Track',
    artist: 'Test Artist',
    album: 'Test Album',
    duration: 200,
    file_path: '/path/to/track2.mp3',
    genre: 'Rock',
    year: 2024,
  },
]

export const mockAlbum = {
  id: 1,
  title: 'Test Album',
  artist: 'Test Artist',
  year: 2024,
  artwork_path: '/path/to/artwork.jpg',
  track_count: 10,
}

export const mockAlbums = [
  mockAlbum,
  {
    id: 2,
    title: 'Another Album',
    artist: 'Test Artist',
    year: 2023,
    artwork_path: '/path/to/artwork2.jpg',
    track_count: 12,
  },
]

export const mockArtist = {
  id: 1,
  name: 'Test Artist',
  album_count: 3,
  track_count: 30,
}

export const mockPlaylist = {
  id: 1,
  name: 'Test Playlist',
  track_count: 5,
  duration: 900,
}

export const mockPlayerState = {
  currentTrack: mockTrack,
  isPlaying: false,
  volume: 0.8,
  currentTime: 0,
  duration: 180,
  queue: mockTracks,
  queueIndex: 0,
  repeat: 'none',
  shuffle: false,
}

export const mockProcessingJob = {
  job_id: 'test-job-123',
  status: 'processing',
  progress: 50,
  message: 'Processing audio...',
  input_file: '/path/to/input.mp3',
  output_file: null,
  preset: 'adaptive',
  created_at: new Date().toISOString(),
}

export const mockLibraryStats = {
  total_tracks: 100,
  total_albums: 10,
  total_artists: 5,
  total_duration: 36000,
  last_scanned: new Date().toISOString(),
}

export const mockScanProgress = {
  status: 'scanning',
  files_scanned: 50,
  files_found: 100,
  current_file: '/path/to/current.mp3',
  errors: [],
}
