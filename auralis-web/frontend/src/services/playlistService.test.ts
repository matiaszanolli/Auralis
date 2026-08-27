/**
 * Playlist Service Tests
 *
 * Tests for the playlist service API layer,
 * including all CRUD operations and error handling.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import * as playlistService from './playlistService'
import * as apiRequest from '../utils/apiRequest'

// Mock the apiRequest module
vi.mock('../utils/apiRequest', () => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  del: vi.fn(),
}))

const mockPlaylist = {
  id: 1,
  name: 'Test Playlist',
  description: 'Test description',
  track_count: 5,
  total_duration: 1200,
}

describe('PlaylistService', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('getPlaylists', () => {
    it('fetches a single page when it is the whole collection', async () => {
      const mockResponse = {
        playlists: [mockPlaylist],
        total: 1,
        offset: 0,
        limit: 200,
        has_more: false,
      }

      vi.mocked(apiRequest.get).mockResolvedValue(mockResponse)

      const result = await playlistService.getPlaylists()

      // #4607: list/get now carry runtime shape guards.
      // #4554: the endpoint is paginated, so the service asks for the maximum
      // page size rather than inheriting the server's default of 50.
      expect(apiRequest.get).toHaveBeenCalledWith('/api/playlists?limit=200&offset=0', {
        validate: expect.any(Function),
      })
      expect(apiRequest.get).toHaveBeenCalledTimes(1)
      expect(result).toEqual({
        playlists: [mockPlaylist],
        total: 1,
        offset: 0,
        limit: 200,
        has_more: false,
      })
    })

    it('aggregates every page until has_more is false (#4832)', async () => {
      const secondPlaylist = { ...mockPlaylist, id: 2 }
      vi.mocked(apiRequest.get)
        .mockResolvedValueOnce({ playlists: [mockPlaylist], total: 2, offset: 0, limit: 200, has_more: true })
        .mockResolvedValueOnce({ playlists: [secondPlaylist], total: 2, offset: 1, limit: 200, has_more: false })

      const result = await playlistService.getPlaylists()

      expect(apiRequest.get).toHaveBeenNthCalledWith(1, '/api/playlists?limit=200&offset=0', {
        validate: expect.any(Function),
      })
      // Second page's offset advances by the first page's actual length, not
      // a fixed page size — correct even if a page returns fewer than `limit`.
      expect(apiRequest.get).toHaveBeenNthCalledWith(2, '/api/playlists?limit=200&offset=1', {
        validate: expect.any(Function),
      })
      expect(apiRequest.get).toHaveBeenCalledTimes(2)
      expect(result.playlists).toEqual([mockPlaylist, secondPlaylist])
      expect(result.total).toBe(2)
      expect(result.has_more).toBe(false)
    })

    it('passes explicit pagination params through (#4554)', async () => {
      vi.mocked(apiRequest.get).mockResolvedValue({ playlists: [], total: 0 })

      await playlistService.getPlaylists({ limit: 25, offset: 50 })

      expect(apiRequest.get).toHaveBeenCalledWith('/api/playlists?limit=25&offset=50', {
        validate: expect.any(Function),
      })
    })

    it('falls back to the page length when the response is a bare array', async () => {
      vi.mocked(apiRequest.get).mockResolvedValue([mockPlaylist])

      const result = await playlistService.getPlaylists()

      expect(result.playlists).toEqual([mockPlaylist])
      expect(result.total).toBe(1)
    })

    it('throws error on fetch failure', async () => {
      vi.mocked(apiRequest.get).mockRejectedValue(new Error('Failed to get playlists'))

      await expect(playlistService.getPlaylists()).rejects.toThrow('Failed to get playlists')
    })

    it('handles network errors', async () => {
      vi.mocked(apiRequest.get).mockRejectedValue(new Error('Network error'))

      await expect(playlistService.getPlaylists()).rejects.toThrow('Network error')
    })
  })

  describe('getPlaylist', () => {
    it('fetches single playlist by ID', async () => {
      vi.mocked(apiRequest.get).mockResolvedValue(mockPlaylist)

      const result = await playlistService.getPlaylist(1)

      expect(apiRequest.get).toHaveBeenCalledWith('/api/playlists/1', { validate: expect.any(Function) })
      expect(result).toEqual(mockPlaylist)
    })

    it('throws error when playlist not found', async () => {
      vi.mocked(apiRequest.get).mockRejectedValue(new Error('Playlist not found'))

      await expect(playlistService.getPlaylist(999)).rejects.toThrow('Playlist not found')
    })
  })

  describe('createPlaylist', () => {
    it('creates playlist successfully', async () => {
      const request = {
        name: 'New Playlist',
        description: 'New description',
      }

      const mockResponse = {
        message: 'Playlist created',
        playlist: mockPlaylist,
      }

      vi.mocked(apiRequest.post).mockResolvedValue(mockResponse)

      const result = await playlistService.createPlaylist(request)

      expect(apiRequest.post).toHaveBeenCalledWith('/api/playlists', request)
      expect(result).toEqual(mockPlaylist)
    })

    it('creates playlist with track IDs', async () => {
      const request = {
        name: 'New Playlist',
        description: '',
        track_ids: [1, 2, 3],
      }

      vi.mocked(apiRequest.post).mockResolvedValue({ playlist: mockPlaylist })

      await playlistService.createPlaylist(request)

      expect(apiRequest.post).toHaveBeenCalledWith('/api/playlists', request)
    })

    it('throws error on creation failure', async () => {
      vi.mocked(apiRequest.post).mockRejectedValue(new Error('Validation error'))

      await expect(
        playlistService.createPlaylist({ name: '', description: '' })
      ).rejects.toThrow('Validation error')
    })
  })

  describe('updatePlaylist', () => {
    it('updates playlist successfully', async () => {
      const updates = {
        name: 'Updated Playlist',
        description: 'Updated description',
      }

      vi.mocked(apiRequest.put).mockResolvedValue({})

      await playlistService.updatePlaylist(1, updates)

      expect(apiRequest.put).toHaveBeenCalledWith('/api/playlists/1', updates)
    })

    it('throws error when playlist not found', async () => {
      vi.mocked(apiRequest.put).mockRejectedValue(new Error('Playlist not found'))

      await expect(
        playlistService.updatePlaylist(999, { name: 'Test' })
      ).rejects.toThrow('Playlist not found')
    })
  })

  describe('deletePlaylist', () => {
    it('deletes playlist successfully', async () => {
      vi.mocked(apiRequest.del).mockResolvedValue({})

      await playlistService.deletePlaylist(1)

      expect(apiRequest.del).toHaveBeenCalledWith('/api/playlists/1')
    })

    it('throws error when playlist not found', async () => {
      vi.mocked(apiRequest.del).mockRejectedValue(new Error('Playlist not found'))

      await expect(playlistService.deletePlaylist(999)).rejects.toThrow('Playlist not found')
    })
  })

  describe('addTrackToPlaylist', () => {
    it('adds track successfully', async () => {
      vi.mocked(apiRequest.post).mockResolvedValue({})

      await playlistService.addTrackToPlaylist(1, 5)

      expect(apiRequest.post).toHaveBeenCalledWith('/api/playlists/1/tracks', { track_ids: [5] })
    })

    it('throws error when track already in playlist', async () => {
      vi.mocked(apiRequest.post).mockRejectedValue(new Error('Track already in playlist'))

      await expect(playlistService.addTrackToPlaylist(1, 5)).rejects.toThrow(
        'Track already in playlist'
      )
    })
  })

  describe('removeTrackFromPlaylist', () => {
    it('removes track successfully', async () => {
      vi.mocked(apiRequest.del).mockResolvedValue({})

      await playlistService.removeTrackFromPlaylist(1, 5)

      expect(apiRequest.del).toHaveBeenCalledWith('/api/playlists/1/tracks/5')
    })

    it('throws error when track not in playlist', async () => {
      vi.mocked(apiRequest.del).mockRejectedValue(new Error('Track not found in playlist'))

      await expect(playlistService.removeTrackFromPlaylist(1, 999)).rejects.toThrow(
        'Track not found in playlist'
      )
    })
  })

  describe('Error Handling', () => {
    it('handles malformed JSON response', async () => {
      vi.mocked(apiRequest.get).mockRejectedValue(new Error('Invalid JSON'))

      await expect(playlistService.getPlaylists()).rejects.toThrow()
    })

    it('provides default error message when detail is missing', async () => {
      vi.mocked(apiRequest.get).mockRejectedValue(new Error('Request failed'))

      await expect(playlistService.getPlaylists()).rejects.toThrow()
    })
  })
})
