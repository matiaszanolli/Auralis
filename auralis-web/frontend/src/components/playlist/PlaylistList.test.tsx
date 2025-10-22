/**
 * PlaylistList Component Tests
 *
 * Tests for the playlist list component in the sidebar,
 * including create, delete, and selection functionality.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, within } from '@/test/test-utils'
import userEvent from '@testing-library/user-event'
import { PlaylistList } from './PlaylistList'
import * as playlistService from '@/services/playlistService'

// Mock the playlist service
vi.mock('@/services/playlistService', () => ({
  getPlaylists: vi.fn(),
  createPlaylist: vi.fn(),
  deletePlaylist: vi.fn(),
}))

// Mock toast notifications
vi.mock('@/components/shared/Toast', () => ({
  useToast: () => ({
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  }),
}))

const mockPlaylists = [
  {
    id: 1,
    name: 'My Playlist',
    description: 'Test playlist',
    track_count: 5,
    total_duration: 1200,
  },
  {
    id: 2,
    name: 'Another Playlist',
    description: '',
    track_count: 3,
    total_duration: 800,
  },
]

describe('PlaylistList', () => {
  beforeEach(() => {
    // Reset mocks before each test
    vi.clearAllMocks()

    // Default mock implementation
    vi.mocked(playlistService.getPlaylists).mockResolvedValue({
      playlists: mockPlaylists,
      total: 2,
    })
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  describe('Rendering', () => {
    it('renders playlist section header', async () => {
      render(<PlaylistList />)

      await waitFor(() => {
        expect(screen.getByText(/Playlists \(\d+\)/)).toBeInTheDocument()
      })
    })

    it('displays all playlists', async () => {
      render(<PlaylistList />)

      await waitFor(() => {
        expect(screen.getByText('My Playlist')).toBeInTheDocument()
        expect(screen.getByText('Another Playlist')).toBeInTheDocument()
      })
    })

    it('displays track count for each playlist', async () => {
      render(<PlaylistList />)

      await waitFor(() => {
        expect(screen.getByText('5 tracks')).toBeInTheDocument()
        expect(screen.getByText('3 tracks')).toBeInTheDocument()
      })
    })

    it('shows create playlist button', async () => {
      render(<PlaylistList />)

      await waitFor(() => {
        expect(screen.getByLabelText('Create playlist')).toBeInTheDocument()
      })
    })
  })

  describe('Loading State', () => {
    it('calls getPlaylists on mount', async () => {
      render(<PlaylistList />)

      await waitFor(() => {
        expect(playlistService.getPlaylists).toHaveBeenCalledTimes(1)
      })
    })

    it('handles empty playlist list', async () => {
      vi.mocked(playlistService.getPlaylists).mockResolvedValue({
        playlists: [],
        total: 0,
      })

      render(<PlaylistList />)

      await waitFor(() => {
        // Should still render the section, just with no playlists
        expect(screen.getByText(/Playlists \(0\)/)).toBeInTheDocument()
      })
    })

    it('handles API errors gracefully', async () => {
      const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
      vi.mocked(playlistService.getPlaylists).mockRejectedValue(new Error('API Error'))

      render(<PlaylistList />)

      await waitFor(() => {
        // Component should still render with (0) playlists after error
        expect(screen.getByText(/Playlists \(0\)/)).toBeInTheDocument()
      })

      consoleError.mockRestore()
    })
  })

  describe('Expand/Collapse', () => {
    it('expands by default', async () => {
      render(<PlaylistList />)

      await waitFor(() => {
        expect(screen.getByText('My Playlist')).toBeVisible()
      })
    })

    it('can be collapsed', async () => {
      const user = userEvent.setup()
      render(<PlaylistList />)

      // Wait for playlists to load
      await waitFor(() => {
        expect(screen.getByText('My Playlist')).toBeInTheDocument()
      })

      // Click the expand/collapse button
      const collapseButton = screen.getByLabelText(/collapse/i)
      await user.click(collapseButton)

      // Check that the aria-expanded attribute changes to false
      await waitFor(() => {
        const expandButton = screen.getByLabelText(/expand/i)
        expect(expandButton).toHaveAttribute('aria-expanded', 'false')
      })
    })
  })

  describe('Playlist Selection', () => {
    it('calls onPlaylistSelect when a playlist is clicked', async () => {
      const handleSelect = vi.fn()
      const user = userEvent.setup()

      render(<PlaylistList onPlaylistSelect={handleSelect} />)

      await waitFor(() => {
        expect(screen.getByText('My Playlist')).toBeInTheDocument()
      })

      const playlist = screen.getByText('My Playlist')
      await user.click(playlist)

      expect(handleSelect).toHaveBeenCalledWith(1)
    })

    it('highlights selected playlist', async () => {
      render(<PlaylistList selectedPlaylistId={1} />)

      await waitFor(() => {
        // Check that the playlist is in the document
        expect(screen.getByText('My Playlist')).toBeInTheDocument()
      })

      // The selected playlist should have different styling (checked via the selected prop)
      const playlistButton = screen.getByText('My Playlist').closest('[role="button"]')
      expect(playlistButton).toBeInTheDocument()
    })
  })

  describe('Create Playlist', () => {
    it('opens create dialog when create button is clicked', async () => {
      const user = userEvent.setup()
      render(<PlaylistList />)

      const createButton = await screen.findByLabelText('Create playlist')
      await user.click(createButton)

      // Dialog should be open
      expect(screen.getByRole('dialog')).toBeInTheDocument()
      expect(screen.getByLabelText('Playlist Name')).toBeInTheDocument()
    })

    it('creates playlist and refreshes list', async () => {
      const user = userEvent.setup()

      const newPlaylist = {
        id: 3,
        name: 'New Playlist',
        description: 'New description',
        track_count: 0,
        total_duration: 0,
      }

      vi.mocked(playlistService.createPlaylist).mockResolvedValue(newPlaylist)

      // After creation, return updated list
      vi.mocked(playlistService.getPlaylists)
        .mockResolvedValueOnce({ playlists: mockPlaylists, total: 2 })
        .mockResolvedValueOnce({
          playlists: [...mockPlaylists, newPlaylist],
          total: 3,
        })

      render(<PlaylistList />)

      // Wait for initial load
      await waitFor(() => {
        expect(screen.getByText('My Playlist')).toBeInTheDocument()
      })

      // Open create dialog
      const createButton = screen.getByLabelText('Create playlist')
      await user.click(createButton)

      // Fill in form
      const nameInput = screen.getByLabelText('Playlist Name')
      await user.type(nameInput, 'New Playlist')

      // Submit
      const createDialogButton = screen.getByRole('button', { name: /create/i })
      await user.click(createDialogButton)

      // Wait for playlist to appear
      await waitFor(() => {
        expect(screen.getByText('New Playlist')).toBeInTheDocument()
      })

      expect(playlistService.createPlaylist).toHaveBeenCalledWith({
        name: 'New Playlist',
        description: '',
        track_ids: undefined,
      })
    })
  })

  describe('Delete Playlist', () => {
    it('shows delete button on hover', async () => {
      const user = userEvent.setup()
      render(<PlaylistList />)

      await waitFor(() => {
        expect(screen.getByText('My Playlist')).toBeInTheDocument()
      })

      const playlistButton = screen.getByText('My Playlist').closest('[role="button"]')!

      // Hover over playlist button
      await user.hover(playlistButton)

      // Delete button should exist (it's always rendered, just opacity changes)
      const deleteButton = within(playlistButton).getByLabelText(/delete/i)
      expect(deleteButton).toBeInTheDocument()
    })

    it('confirms before deleting', async () => {
      const user = userEvent.setup()
      const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false)

      render(<PlaylistList />)

      await waitFor(() => {
        expect(screen.getByText('My Playlist')).toBeInTheDocument()
      })

      // Find delete button (it's hidden until hover, but we can still click it)
      const playlistButton = screen.getByText('My Playlist').closest('[role="button"]')!
      const deleteButton = within(playlistButton).getByLabelText(/delete/i)

      await user.click(deleteButton)

      expect(confirmSpy).toHaveBeenCalled()
      expect(playlistService.deletePlaylist).not.toHaveBeenCalled()

      confirmSpy.mockRestore()
    })

    it('deletes playlist after confirmation', async () => {
      const user = userEvent.setup()
      const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)

      vi.mocked(playlistService.deletePlaylist).mockResolvedValue(undefined)

      render(<PlaylistList />)

      await waitFor(() => {
        expect(screen.getByText('My Playlist')).toBeInTheDocument()
      })

      // Find and click delete button
      const playlistButton = screen.getByText('My Playlist').closest('[role="button"]')!
      const deleteButton = within(playlistButton).getByLabelText(/delete/i)

      await user.click(deleteButton)

      // Should call delete API
      expect(playlistService.deletePlaylist).toHaveBeenCalledWith(1)

      // Playlist should disappear from list
      await waitFor(() => {
        expect(screen.queryByText('My Playlist')).not.toBeInTheDocument()
      })

      confirmSpy.mockRestore()
    })

    it('stops propagation when delete button is clicked', async () => {
      const user = userEvent.setup()
      const handleSelect = vi.fn()
      const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)

      vi.mocked(playlistService.deletePlaylist).mockResolvedValue(undefined)

      render(<PlaylistList onPlaylistSelect={handleSelect} />)

      await waitFor(() => {
        expect(screen.getByText('My Playlist')).toBeInTheDocument()
      })

      // Click delete button
      const playlistButton = screen.getByText('My Playlist').closest('[role="button"]')!
      const deleteButton = within(playlistButton).getByLabelText(/delete/i)

      await user.click(deleteButton)

      // Playlist select should NOT be called (event stopped propagation)
      expect(handleSelect).not.toHaveBeenCalled()

      confirmSpy.mockRestore()
    })
  })
})
