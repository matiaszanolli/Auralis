/**
 * Playlist Service Tests
 *
 * Tests for the playlist service API layer,
 * including all CRUD operations and error handling.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import * as playlistService from './playlistService'

// Mock fetch globally
global.fetch = vi.fn()

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
    it('fetches all playlists successfully', async () => {
      const mockResponse = {
        playlists: [mockPlaylist],
        total: 1,
      }

      vi.mocked(fetch).mockResolvedValue({
        ok: true,
        json: async () => mockResponse,
      } as Response)

      const result = await playlistService.getPlaylists()

      expect(fetch).toHaveBeenCalledWith('/api/playlists')
      expect(result).toEqual(mockResponse)
    })

    it('throws error on fetch failure', async () => {
      vi.mocked(fetch).mockResolvedValue({
        ok: false,
        statusText: 'Internal Server Error',
      } as Response)

      await expect(playlistService.getPlaylists()).rejects.toThrow('Failed to get playlists')
    })

    it('handles network errors', async () => {
      vi.mocked(fetch).mockRejectedValue(new Error('Network error'))

      await expect(playlistService.getPlaylists()).rejects.toThrow('Network error')
    })
  })

  describe('getPlaylist', () => {
    it('fetches single playlist by ID', async () => {
      // Service returns the whole response, so mock should return playlist directly
      vi.mocked(fetch).mockResolvedValue({
        ok: true,
        json: async () => mockPlaylist,
      } as Response)

      const result = await playlistService.getPlaylist(1)

      expect(fetch).toHaveBeenCalledWith('/api/playlists/1')
      expect(result).toEqual(mockPlaylist)
    })

    it('throws error when playlist not found', async () => {
      vi.mocked(fetch).mockResolvedValue({
        ok: false,
        json: async () => ({ detail: 'Playlist not found' }),
      } as Response)

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

      vi.mocked(fetch).mockResolvedValue({
        ok: true,
        json: async () => mockResponse,
      } as Response)

      const result = await playlistService.createPlaylist(request)

      expect(fetch).toHaveBeenCalledWith('/api/playlists', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
      })
      expect(result).toEqual(mockPlaylist)
    })

    it('creates playlist with track IDs', async () => {
      const request = {
        name: 'New Playlist',
        description: '',
        track_ids: [1, 2, 3],
      }

      vi.mocked(fetch).mockResolvedValue({
        ok: true,
        json: async () => ({ playlist: mockPlaylist }),
      } as Response)

      await playlistService.createPlaylist(request)

      expect(fetch).toHaveBeenCalledWith(
        '/api/playlists',
        expect.objectContaining({
          body: JSON.stringify(request),
        })
      )
    })

    it('throws error on creation failure', async () => {
      vi.mocked(fetch).mockResolvedValue({
        ok: false,
        json: async () => ({ detail: 'Validation error' }),
      } as Response)

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

      vi.mocked(fetch).mockResolvedValue({
        ok: true,
        json: async () => ({}),
      } as Response)

      await playlistService.updatePlaylist(1, updates)

      expect(fetch).toHaveBeenCalledWith('/api/playlists/1', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates),
      })
    })

    it('throws error when playlist not found', async () => {
      vi.mocked(fetch).mockResolvedValue({
        ok: false,
        json: async () => ({ detail: 'Playlist not found' }),
      } as Response)

      await expect(
        playlistService.updatePlaylist(999, { name: 'Test' })
      ).rejects.toThrow('Playlist not found')
    })
  })

  describe('deletePlaylist', () => {
    it('deletes playlist successfully', async () => {
      const mockResponse = {
        message: 'Playlist deleted',
        playlist_id: 1,
      }

      vi.mocked(fetch).mockResolvedValue({
        ok: true,
        json: async () => mockResponse,
      } as Response)

      await playlistService.deletePlaylist(1)

      expect(fetch).toHaveBeenCalledWith('/api/playlists/1', {
        method: 'DELETE',
      })
    })

    it('throws error when playlist not found', async () => {
      vi.mocked(fetch).mockResolvedValue({
        ok: false,
        json: async () => ({ detail: 'Playlist not found' }),
      } as Response)

      await expect(playlistService.deletePlaylist(999)).rejects.toThrow('Playlist not found')
    })
  })

  describe('addTrackToPlaylist', () => {
    it('adds track successfully', async () => {
      const mockResponse = {
        message: 'Track added to playlist',
        playlist_id: 1,
        track_id: 5,
      }

      vi.mocked(fetch).mockResolvedValue({
        ok: true,
        json: async () => mockResponse,
      } as Response)

      await playlistService.addTrackToPlaylist(1, 5)

      expect(fetch).toHaveBeenCalledWith('/api/playlists/1/tracks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ track_id: 5 }),
      })
    })

    it('throws error when track already in playlist', async () => {
      vi.mocked(fetch).mockResolvedValue({
        ok: false,
        json: async () => ({ detail: 'Track already in playlist' }),
      } as Response)

      await expect(playlistService.addTrackToPlaylist(1, 5)).rejects.toThrow(
        'Track already in playlist'
      )
    })
  })

  describe('removeTrackFromPlaylist', () => {
    it('removes track successfully', async () => {
      const mockResponse = {
        message: 'Track removed from playlist',
        playlist_id: 1,
        track_id: 5,
      }

      vi.mocked(fetch).mockResolvedValue({
        ok: true,
        json: async () => mockResponse,
      } as Response)

      await playlistService.removeTrackFromPlaylist(1, 5)

      expect(fetch).toHaveBeenCalledWith('/api/playlists/1/tracks/5', {
        method: 'DELETE',
      })
    })

    it('throws error when track not in playlist', async () => {
      vi.mocked(fetch).mockResolvedValue({
        ok: false,
        json: async () => ({ detail: 'Track not found in playlist' }),
      } as Response)

      await expect(playlistService.removeTrackFromPlaylist(1, 999)).rejects.toThrow(
        'Track not found in playlist'
      )
    })
  })

  describe('clearPlaylist', () => {
    it('clears playlist successfully', async () => {
      const mockResponse = {
        message: 'Playlist cleared',
        playlist_id: 1,
      }

      vi.mocked(fetch).mockResolvedValue({
        ok: true,
        json: async () => mockResponse,
      } as Response)

      await playlistService.clearPlaylist(1)

      expect(fetch).toHaveBeenCalledWith('/api/playlists/1/tracks', {
        method: 'DELETE',
      })
    })

    it('throws error when playlist not found', async () => {
      vi.mocked(fetch).mockResolvedValue({
        ok: false,
        json: async () => ({ detail: 'Playlist not found' }),
      } as Response)

      await expect(playlistService.clearPlaylist(999)).rejects.toThrow('Playlist not found')
    })
  })

  describe('Error Handling', () => {
    it('handles malformed JSON response', async () => {
      vi.mocked(fetch).mockResolvedValue({
        ok: false,
        json: async () => {
          throw new Error('Invalid JSON')
        },
      } as Response)

      await expect(playlistService.getPlaylists()).rejects.toThrow()
    })

    it('provides default error message when detail is missing', async () => {
      vi.mocked(fetch).mockResolvedValue({
        ok: false,
        json: async () => ({}),
      } as Response)

      await expect(playlistService.getPlaylists()).rejects.toThrow()
    })
  })
})
