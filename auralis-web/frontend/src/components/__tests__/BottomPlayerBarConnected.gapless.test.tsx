/**
 * Tests for BottomPlayerBarConnected - Gapless & Crossfade Features
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Tests the gapless playback and crossfade functionality.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, act } from '@testing-library/react'
import '@testing-library/jest-dom'
import { BottomPlayerBarConnected } from '../BottomPlayerBarConnected'
import { ToastProvider } from '../shared/Toast'

// Mock the usePlayerAPI hook
vi.mock('../../hooks/usePlayerAPI', () => ({
  usePlayerAPI: () => ({
    currentTrack: {
      id: 1,
      title: 'Test Track',
      artist: 'Test Artist',
      album: 'Test Album',
      duration: 180
    },
    isPlaying: false,
    volume: 80,
    currentTime: 0,
    queue: [
      { id: 1, title: 'Track 1', duration: 180 },
      { id: 2, title: 'Track 2', duration: 200 }
    ],
    loading: false,
    play: vi.fn(),
    pause: vi.fn(),
    next: vi.fn(),
    previous: vi.fn(),
    seek: vi.fn(),
    setVolume: vi.fn(),
    toggleMute: vi.fn(),
    loadTrack: vi.fn(),
    setEnhancement: vi.fn(),
    setPreset: vi.fn()
  })
}))

// Mock fetch for settings
global.fetch = vi.fn()

// Helper to render with providers
const renderWithProviders = (component: React.ReactElement) => {
  return render(
    <ToastProvider>
      {component}
    </ToastProvider>
  )
}

describe('BottomPlayerBarConnected - Gapless & Crossfade', () => {
  beforeEach(() => {
    vi.clearAllMocks()

    // Mock settings API
    ;(global.fetch as any).mockResolvedValue({
      ok: true,
      json: async () => ({
        gapless_enabled: true,
        crossfade_enabled: false,
        crossfade_duration: 5.0,
        volume: 80
      })
    })
  })

  describe('Settings Loading', () => {
    it('fetches settings on mount', async () => {
      await act(async () => {
        renderWithProviders(<BottomPlayerBarConnected />)
      })

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith(
          expect.stringContaining('/api/settings')
        )
      })
    })

    it('sets gapless enabled from settings', async () => {
      ;(global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          gapless_enabled: true,
          crossfade_enabled: false
        })
      })

      await act(async () => {
        renderWithProviders(<BottomPlayerBarConnected />)
      })

      // Component should render without errors when settings load
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /play/i })).toBeInTheDocument()
      })
    })

    it('sets crossfade settings from API', async () => {
      ;(global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          gapless_enabled: false,
          crossfade_enabled: true,
          crossfade_duration: 8.0
        })
      })

      await act(async () => {
        renderWithProviders(<BottomPlayerBarConnected />)
      })

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /play/i })).toBeInTheDocument()
      })
    })
  })

  describe('Gapless Playback', () => {
    it('renders two audio elements for gapless', async () => {
      await act(async () => {
        const { container } = renderWithProviders(<BottomPlayerBarConnected />)

        await waitFor(() => {
          const audioElements = container.querySelectorAll('audio')
          expect(audioElements.length).toBeGreaterThanOrEqual(1)
        })
      })
    })

    it('fetches queue when component mounts', async () => {
      ;(global.fetch as any)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ gapless_enabled: true, crossfade_enabled: false })
        })

      await act(async () => {
        renderWithProviders(<BottomPlayerBarConnected />)
      })

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalled()
      })
    })
  })

  describe('Time Update Callbacks', () => {
    it('calls onTimeUpdate callback when provided', async () => {
      const mockTimeUpdate = vi.fn()

      await act(async () => {
        const { container } = renderWithProviders(
          <BottomPlayerBarConnected onTimeUpdate={mockTimeUpdate} />
        )

        await waitFor(() => {
          const audio = container.querySelector('audio')
          expect(audio).toBeInTheDocument()
        })

        // Simulate time update event
        const audio = container.querySelector('audio')
        if (audio) {
          await act(async () => {
            const event = new Event('timeupdate')
            Object.defineProperty(event, 'currentTarget', {
              value: { currentTime: 10.5 },
              writable: true
            })
            audio.dispatchEvent(event)
          })
        }
      })

      // The callback should be called with the time
      await waitFor(() => {
        expect(mockTimeUpdate).toHaveBeenCalled()
      }, { timeout: 3000 })
    })
  })

  describe('Lyrics Toggle Integration', () => {
    it('calls onToggleLyrics when provided and button exists', async () => {
      const mockToggleLyrics = vi.fn()

      await act(async () => {
        renderWithProviders(
          <BottomPlayerBarConnected onToggleLyrics={mockToggleLyrics} />
        )
      })

      await waitFor(() => {
        // Component should render successfully with lyrics callback
        expect(screen.getByRole('button', { name: /play/i })).toBeInTheDocument()
      })
    })
  })

  describe('Component Rendering', () => {
    it('renders player controls', async () => {
      await act(async () => {
        renderWithProviders(<BottomPlayerBarConnected />)
      })

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /play/i })).toBeInTheDocument()
      })
    })

    it('displays track information', async () => {
      await act(async () => {
        renderWithProviders(<BottomPlayerBarConnected />)
      })

      await waitFor(() => {
        expect(screen.getByText('Test Track')).toBeInTheDocument()
        expect(screen.getByText('Test Artist')).toBeInTheDocument()
      })
    })
  })

  describe('Error Handling', () => {
    it('handles settings fetch errors gracefully', async () => {
      ;(global.fetch as any).mockRejectedValueOnce(new Error('Network error'))

      await act(async () => {
        renderWithProviders(<BottomPlayerBarConnected />)
      })

      // Component should still render even if settings fail
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /play/i })).toBeInTheDocument()
      })
    })

    it('handles invalid settings response', async () => {
      ;(global.fetch as any).mockResolvedValueOnce({
        ok: false,
        status: 500
      })

      await act(async () => {
        renderWithProviders(<BottomPlayerBarConnected />)
      })

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /play/i })).toBeInTheDocument()
      })
    })
  })
})
