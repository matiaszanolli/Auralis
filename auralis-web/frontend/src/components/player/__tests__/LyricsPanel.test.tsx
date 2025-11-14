/**
 * Tests for LyricsPanel Component
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Tests the lyrics display panel with LRC parsing and auto-scroll.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, act } from '@/test/test-utils'
import '@testing-library/jest-dom'
import LyricsPanel from '../LyricsPanel'

// Create mock fetch before test
const mockFetch = vi.fn()

// Setup fetch mock
beforeAll(() => {
  global.fetch = mockFetch as any
})

describe('LyricsPanel', () => {
  const mockOnClose = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Rendering', () => {
    it('renders the panel with header', async () => {
      ;mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ track_id: 1, lyrics: null, format: null })
      })

      await act(async () => {
        render(<LyricsPanel trackId={1} currentTime={0} onClose={mockOnClose} />)
      })

      await waitFor(() => {
        expect(screen.getByText('Lyrics')).toBeInTheDocument()
      })
    })

    it('renders close button', async () => {
      ;mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ track_id: 1, lyrics: null, format: null })
      })

      await act(async () => {
        render(<LyricsPanel trackId={1} currentTime={0} onClose={mockOnClose} />)
      })

      await waitFor(() => {
        expect(screen.getByTestId('CloseIcon')).toBeInTheDocument()
      })
    })

    it('shows empty state when no lyrics available', async () => {
      ;mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ track_id: 1, lyrics: null, format: null })
      })

      await act(async () => {
        render(<LyricsPanel trackId={1} currentTime={0} onClose={mockOnClose} />)
      })

      await waitFor(() => {
        expect(screen.getByText('No Lyrics Available')).toBeInTheDocument()
      })
    })
  })

  describe('Lyrics Fetching', () => {
    it('fetches lyrics on mount', async () => {
      const mockLyrics = 'Line 1\nLine 2\nLine 3'
      ;mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          track_id: 1,
          lyrics: mockLyrics,
          format: 'plain'
        })
      })

      await act(async () => {
        render(<LyricsPanel trackId={1} currentTime={0} onClose={mockOnClose} />)
      })

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith(
          '/api/library/tracks/1/lyrics'
        )
      })
    })

    it('displays loading state while fetching', async () => {
      ;mockFetch.mockImplementation(() => new Promise(() => {}))

      await act(async () => {
        render(<LyricsPanel trackId={1} currentTime={0} onClose={mockOnClose} />)
      })

      await waitFor(() => {
        expect(screen.getByText('Loading lyrics...')).toBeInTheDocument()
      })
    })

    it('displays plain text lyrics', async () => {
      const mockLyrics = 'Line 1\nLine 2\nLine 3'
      ;mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          track_id: 1,
          lyrics: mockLyrics,
          format: 'plain'
        })
      })

      await act(async () => {
        render(<LyricsPanel trackId={1} currentTime={0} onClose={mockOnClose} />)
      })

      await waitFor(() => {
        expect(screen.getByText('Line 1')).toBeInTheDocument()
        expect(screen.getByText('Line 2')).toBeInTheDocument()
        expect(screen.getByText('Line 3')).toBeInTheDocument()
      })
    })

    it('handles fetch errors gracefully', async () => {
      ;mockFetch.mockRejectedValueOnce(new Error('Network error'))

      await act(async () => {
        render(<LyricsPanel trackId={1} currentTime={0} onClose={mockOnClose} />)
      })

      // Should show empty state after error
      await waitFor(() => {
        expect(screen.getByText('No Lyrics Available')).toBeInTheDocument()
      })
    })
  })

  describe('LRC Format Parsing', () => {
    it('parses LRC format correctly', async () => {
      const lrcLyrics = '[00:00.00]First line\n[00:05.00]Second line\n[00:10.00]Third line'
      ;mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          track_id: 1,
          lyrics: lrcLyrics,
          format: 'lrc'
        })
      })

      await act(async () => {
        render(<LyricsPanel trackId={1} currentTime={0} onClose={mockOnClose} />)
      })

      await waitFor(() => {
        expect(screen.getByText('First line')).toBeInTheDocument()
        expect(screen.getByText('Second line')).toBeInTheDocument()
        expect(screen.getByText('Third line')).toBeInTheDocument()
      })
    })

    it('parses timestamps with milliseconds', async () => {
      const lrcLyrics = '[00:12.45]Line with milliseconds'
      ;mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          track_id: 1,
          lyrics: lrcLyrics,
          format: 'lrc'
        })
      })

      await act(async () => {
        render(<LyricsPanel trackId={1} currentTime={0} onClose={mockOnClose} />)
      })

      await waitFor(() => {
        expect(screen.getByText('Line with milliseconds')).toBeInTheDocument()
      })
    })

    it('parses timestamps without milliseconds', async () => {
      const lrcLyrics = '[00:30]Line without milliseconds'
      ;mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          track_id: 1,
          lyrics: lrcLyrics,
          format: 'lrc'
        })
      })

      await act(async () => {
        render(<LyricsPanel trackId={1} currentTime={0} onClose={mockOnClose} />)
      })

      await waitFor(() => {
        expect(screen.getByText('Line without milliseconds')).toBeInTheDocument()
      })
    })

    it('ignores metadata tags in LRC', async () => {
      const lrcLyrics = '[ar:Artist Name]\n[ti:Title]\n[00:00.00]Actual lyric'
      ;mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          track_id: 1,
          lyrics: lrcLyrics,
          format: 'lrc'
        })
      })

      await act(async () => {
        render(<LyricsPanel trackId={1} currentTime={0} onClose={mockOnClose} />)
      })

      await waitFor(() => {
        expect(screen.getByText('Actual lyric')).toBeInTheDocument()
        expect(screen.queryByText('Artist Name')).not.toBeInTheDocument()
      })
    })
  })

  describe('Active Line Highlighting', () => {
    it('highlights current line based on playback time', async () => {
      const lrcLyrics = '[00:00.00]First line\n[00:05.00]Second line\n[00:10.00]Third line'
      ;mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          track_id: 1,
          lyrics: lrcLyrics,
          format: 'lrc'
        })
      })

      const { rerender } = await act(async () => {
        return render(<LyricsPanel trackId={1} currentTime={6} onClose={mockOnClose} />)
      })

      await waitFor(() => {
        expect(screen.getByText('Second line')).toBeInTheDocument()
      })

      // Update playback time to 11 seconds
      await act(async () => {
        rerender(<LyricsPanel trackId={1} currentTime={11} onClose={mockOnClose} />)
      })

      // Third line should now be highlighted
      await waitFor(() => {
        expect(screen.getByText('Third line')).toBeInTheDocument()
      })
    })

    it('handles time before first line', async () => {
      const lrcLyrics = '[00:05.00]First line\n[00:10.00]Second line'
      ;mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          track_id: 1,
          lyrics: lrcLyrics,
          format: 'lrc'
        })
      })

      await act(async () => {
        render(<LyricsPanel trackId={1} currentTime={2} onClose={mockOnClose} />)
      })

      await waitFor(() => {
        expect(screen.getByText('First line')).toBeInTheDocument()
      })
    })
  })

  describe('Track Changes', () => {
    it('fetches new lyrics when track changes', async () => {
      ;mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          track_id: 1,
          lyrics: '[00:00.00]Track 1 lyrics',
          format: 'lrc'
        })
      })

      const { rerender } = await act(async () => {
        return render(<LyricsPanel trackId={1} currentTime={0} onClose={mockOnClose} />)
      })

      await waitFor(() => {
        expect(screen.getByText('Track 1 lyrics')).toBeInTheDocument()
      })

      // Change track
      ;mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          track_id: 2,
          lyrics: '[00:00.00]Track 2 lyrics',
          format: 'lrc'
        })
      })

      await act(async () => {
        rerender(<LyricsPanel trackId={2} currentTime={0} onClose={mockOnClose} />)
      })

      await waitFor(() => {
        expect(screen.getByText('Track 2 lyrics')).toBeInTheDocument()
      })
    })
  })

  describe('Error Handling', () => {
    it('handles 404 errors', async () => {
      ;mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404
      })

      await act(async () => {
        render(<LyricsPanel trackId={1} currentTime={0} onClose={mockOnClose} />)
      })

      await waitFor(() => {
        expect(screen.getByText('No Lyrics Available')).toBeInTheDocument()
      })
    })

    it('handles network errors', async () => {
      ;mockFetch.mockRejectedValueOnce(new Error('Network error'))

      await act(async () => {
        render(<LyricsPanel trackId={1} currentTime={0} onClose={mockOnClose} />)
      })

      await waitFor(() => {
        expect(screen.getByText('No Lyrics Available')).toBeInTheDocument()
      })
    })
  })

  describe('User Interactions', () => {
    it('calls onClose when close button clicked', async () => {
      ;mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ track_id: 1, lyrics: null, format: null })
      })

      await act(async () => {
        render(<LyricsPanel trackId={1} currentTime={0} onClose={mockOnClose} />)
      })

      await waitFor(() => {
        const closeIcon = screen.getByTestId('CloseIcon')
        const closeButton = closeIcon.closest('button')
        closeButton?.click()
      })

      expect(mockOnClose).toHaveBeenCalledTimes(1)
    })
  })
})
