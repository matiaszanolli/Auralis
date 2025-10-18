/**
 * Tests for BottomPlayerBar component
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@/test/test-utils'
import BottomPlayerBar from '../BottomPlayerBar'
import { mockFetch, mockApiEndpoint, mockTrack, mockPlayerState } from '@/test/mocks/api'

// Mock the usePlayerAPI hook
vi.mock('../../hooks/usePlayerAPI', () => ({
  usePlayerAPI: () => ({
    currentTrack: mockTrack,
    isPlaying: false,
    currentTime: 30,
    duration: 180,
    volume: 80,
    queue: [mockTrack],
    play: vi.fn(),
    pause: vi.fn(),
    resume: vi.fn(),
    next: vi.fn(),
    previous: vi.fn(),
    seek: vi.fn(),
    setVolume: vi.fn(),
    loading: false,
    error: null,
  }),
}))

describe('BottomPlayerBar', () => {
  beforeEach(() => {
    mockFetch()
    mockApiEndpoint('/api/player/status', mockPlayerState)
  })

  it('renders current track information', () => {
    render(<BottomPlayerBar />)

    expect(screen.getByText(mockTrack.title)).toBeInTheDocument()
    expect(screen.getByText(mockTrack.artist)).toBeInTheDocument()
  })

  it('displays playback controls', () => {
    render(<BottomPlayerBar />)

    // Should show play/pause, previous, and next buttons
    expect(screen.getByLabelText(/play|pause/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/previous/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/next/i)).toBeInTheDocument()
  })

  it('shows current time and duration', () => {
    render(<BottomPlayerBar />)

    // Format: 0:30 / 3:00
    expect(screen.getByText(/0:30/)).toBeInTheDocument()
    expect(screen.getByText(/3:00/)).toBeInTheDocument()
  })

  it('displays progress bar', () => {
    render(<BottomPlayerBar />)

    const progressBar = screen.getByRole('slider', { name: /progress/i })
    expect(progressBar).toBeInTheDocument()
  })

  it('updates progress bar based on currentTime', () => {
    render(<BottomPlayerBar />)

    const progressBar = screen.getByRole('slider', { name: /progress/i })
    // Progress should be (30/180) * 100 = 16.67%
    expect(progressBar).toHaveAttribute('aria-valuenow', '16.67')
  })

  it('displays volume control', () => {
    render(<BottomPlayerBar />)

    const volumeSlider = screen.getByRole('slider', { name: /volume/i })
    expect(volumeSlider).toBeInTheDocument()
    expect(volumeSlider).toHaveAttribute('aria-valuenow', '80')
  })

  it('shows album artwork', () => {
    render(<BottomPlayerBar />)

    const artwork = screen.getByRole('img', { name: /album art/i })
    expect(artwork).toBeInTheDocument()
  })

  it('displays empty state when no track is playing', () => {
    // Re-mock the hook to return null track
    vi.clearAllMocks()
    vi.mock('../../hooks/usePlayerAPI', () => ({
      usePlayerAPI: () => ({
        currentTrack: null,
        isPlaying: false,
        currentTime: 0,
        duration: 0,
        volume: 80,
        queue: [],
        play: vi.fn(),
        pause: vi.fn(),
        resume: vi.fn(),
        next: vi.fn(),
        previous: vi.fn(),
        seek: vi.fn(),
        setVolume: vi.fn(),
        loading: false,
        error: null,
      }),
    }))

    render(<BottomPlayerBar />)

    expect(screen.getByText(/no track playing/i)).toBeInTheDocument()
  })

  it('shows repeat and shuffle controls', () => {
    render(<BottomPlayerBar />)

    expect(screen.getByLabelText(/repeat/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/shuffle/i)).toBeInTheDocument()
  })

  it('calls play handler when play button is clicked', async () => {
    const mockPlay = vi.fn()

    vi.mock('../../hooks/usePlayerAPI', () => ({
      usePlayerAPI: () => ({
        currentTrack: mockTrack,
        isPlaying: false,
        play: mockPlay,
        pause: vi.fn(),
        resume: vi.fn(),
        next: vi.fn(),
        previous: vi.fn(),
        seek: vi.fn(),
        setVolume: vi.fn(),
        currentTime: 0,
        duration: 180,
        volume: 80,
        queue: [mockTrack],
        loading: false,
        error: null,
      }),
    }))

    render(<BottomPlayerBar />)

    const playButton = screen.getByLabelText(/play/i)
    fireEvent.click(playButton)

    await waitFor(() => {
      expect(mockPlay).toHaveBeenCalled()
    })
  })

  it('calls seek handler when progress bar is changed', async () => {
    const mockSeek = vi.fn()

    vi.mock('../../hooks/usePlayerAPI', () => ({
      usePlayerAPI: () => ({
        currentTrack: mockTrack,
        isPlaying: true,
        play: vi.fn(),
        pause: vi.fn(),
        resume: vi.fn(),
        next: vi.fn(),
        previous: vi.fn(),
        seek: mockSeek,
        setVolume: vi.fn(),
        currentTime: 30,
        duration: 180,
        volume: 80,
        queue: [mockTrack],
        loading: false,
        error: null,
      }),
    }))

    render(<BottomPlayerBar />)

    const progressBar = screen.getByRole('slider', { name: /progress/i })
    fireEvent.change(progressBar, { target: { value: 90 } })

    await waitFor(() => {
      expect(mockSeek).toHaveBeenCalledWith(90)
    })
  })

  it('calls setVolume handler when volume slider is changed', async () => {
    const mockSetVolume = vi.fn()

    vi.mock('../../hooks/usePlayerAPI', () => ({
      usePlayerAPI: () => ({
        currentTrack: mockTrack,
        isPlaying: false,
        play: vi.fn(),
        pause: vi.fn(),
        resume: vi.fn(),
        next: vi.fn(),
        previous: vi.fn(),
        seek: vi.fn(),
        setVolume: mockSetVolume,
        currentTime: 30,
        duration: 180,
        volume: 80,
        queue: [mockTrack],
        loading: false,
        error: null,
      }),
    }))

    render(<BottomPlayerBar />)

    const volumeSlider = screen.getByRole('slider', { name: /volume/i })
    fireEvent.change(volumeSlider, { target: { value: 50 } })

    await waitFor(() => {
      expect(mockSetVolume).toHaveBeenCalledWith(50)
    })
  })
})
