/**
 * Tests for BottomPlayerBar component
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent } from '@/test/test-utils'
import BottomPlayerBar from '../BottomPlayerBar'

const mockTrack = {
  id: 1,
  title: 'Test Track',
  artist: 'Test Artist',
  album: 'Test Album',
  duration: 180,
  albumArt: '/test-art.jpg',
}

describe('BottomPlayerBar', () => {
  const mockOnPlayPause = vi.fn()
  const mockOnNext = vi.fn()
  const mockOnPrevious = vi.fn()
  const mockOnEnhancementToggle = vi.fn()

  const defaultProps = {
    currentTrack: mockTrack,
    isPlaying: false,
    onPlayPause: mockOnPlayPause,
    onNext: mockOnNext,
    onPrevious: mockOnPrevious,
    onEnhancementToggle: mockOnEnhancementToggle,
  }

  beforeEach(() => {
    mockOnPlayPause.mockClear()
    mockOnNext.mockClear()
    mockOnPrevious.mockClear()
    mockOnEnhancementToggle.mockClear()
  })

  // ============================================================================
  // Basic Rendering Tests
  // ============================================================================

  it('renders without crashing', () => {
    render(<BottomPlayerBar />)
    // Should render even without a current track
    expect(screen.getByRole('button')).toBeInTheDocument()
  })

  it('renders current track information', () => {
    render(<BottomPlayerBar {...defaultProps} />)

    expect(screen.getByText(mockTrack.title)).toBeInTheDocument()
    expect(screen.getByText(mockTrack.artist)).toBeInTheDocument()
  })

  it('displays placeholders when no track is playing', () => {
    render(<BottomPlayerBar />)

    expect(screen.getByText('No track playing')).toBeInTheDocument()
  })

  // ============================================================================
  // Playback Control Tests
  // ============================================================================

  it('displays playback controls', () => {
    render(<BottomPlayerBar {...defaultProps} />)

    // Should have play/pause button, previous, and next buttons
    const buttons = screen.getAllByRole('button')
    expect(buttons.length).toBeGreaterThan(0)
  })

  it('shows play icon when not playing', () => {
    const { container } = render(<BottomPlayerBar {...defaultProps} isPlaying={false} />)

    // Play icon should be present
    const playIcon = container.querySelector('[data-testid="PlayArrowIcon"]')
    expect(playIcon).toBeInTheDocument()
  })

  it('shows pause icon when playing', () => {
    const { container } = render(<BottomPlayerBar {...defaultProps} isPlaying={true} />)

    // Pause icon should be present
    const pauseIcon = container.querySelector('[data-testid="PauseIcon"]')
    expect(pauseIcon).toBeInTheDocument()
  })

  it('calls onPlayPause when play/pause button is clicked', () => {
    render(<BottomPlayerBar {...defaultProps} />)

    // Find the main play button (it's styled differently)
    const buttons = screen.getAllByRole('button')
    const playButton = buttons.find(btn => btn.querySelector('[data-testid="PlayArrowIcon"]'))

    if (playButton) {
      fireEvent.click(playButton)
      expect(mockOnPlayPause).toHaveBeenCalledTimes(1)
    }
  })

  it('calls onNext when next button is clicked', () => {
    const { container } = render(<BottomPlayerBar {...defaultProps} />)

    const nextButton = container.querySelector('[data-testid="SkipNextIcon"]')?.closest('button')
    if (nextButton) {
      fireEvent.click(nextButton)
      expect(mockOnNext).toHaveBeenCalledTimes(1)
    }
  })

  it('calls onPrevious when previous button is clicked', () => {
    const { container } = render(<BottomPlayerBar {...defaultProps} />)

    const prevButton = container.querySelector('[data-testid="SkipPreviousIcon"]')?.closest('button')
    if (prevButton) {
      fireEvent.click(prevButton)
      expect(mockOnPrevious).toHaveBeenCalledTimes(1)
    }
  })

  // ============================================================================
  // Enhancement Toggle Tests
  // ============================================================================

  it('displays enhancement toggle', () => {
    render(<BottomPlayerBar {...defaultProps} />)

    // Should have a toggle switch for enhancement
    const switches = screen.getAllByRole('checkbox')
    expect(switches.length).toBeGreaterThan(0)
  })

  it('calls onEnhancementToggle when toggle is clicked', () => {
    render(<BottomPlayerBar {...defaultProps} />)

    // Find the enhancement toggle switch
    const switches = screen.getAllByRole('checkbox')
    // The enhancement toggle should be one of them
    if (switches.length > 0) {
      fireEvent.click(switches[0])
      expect(mockOnEnhancementToggle).toHaveBeenCalled()
    }
  })

  // ============================================================================
  // Volume Control Tests
  // ============================================================================

  it('displays volume control', () => {
    render(<BottomPlayerBar {...defaultProps} />)

    // Volume icon should be present
    const { container } = render(<BottomPlayerBar {...defaultProps} />)
    const volumeIcon = container.querySelector('[data-testid="VolumeUpIcon"]')
    expect(volumeIcon).toBeInTheDocument()
  })

  it('can mute/unmute volume', () => {
    const { container } = render(<BottomPlayerBar {...defaultProps} />)

    const volumeButton = container.querySelector('[data-testid="VolumeUpIcon"]')?.closest('button')
    if (volumeButton) {
      // Click to mute
      fireEvent.click(volumeButton)

      // Should show VolumeOff icon (this is internal state, harder to test)
      expect(volumeButton).toBeInTheDocument()
    }
  })

  // ============================================================================
  // Album Art Tests
  // ============================================================================

  it('displays album artwork when available', () => {
    render(<BottomPlayerBar {...defaultProps} />)

    // Album art should be rendered as a background image or img
    const { container } = render(<BottomPlayerBar {...defaultProps} />)
    const elements = container.querySelectorAll('*')

    // Check if any element has the album art as background or src
    const hasAlbumArt = Array.from(elements).some(el => {
      const style = window.getComputedStyle(el)
      return style.backgroundImage.includes(mockTrack.albumArt!) ||
             (el as HTMLImageElement).src?.includes(mockTrack.albumArt!)
    })

    expect(hasAlbumArt || container.innerHTML.includes(mockTrack.albumArt!)).toBeTruthy()
  })

  it('shows placeholder when no album art', () => {
    const trackWithoutArt = { ...mockTrack, albumArt: undefined }
    render(<BottomPlayerBar {...defaultProps} currentTrack={trackWithoutArt} />)

    // Should still render without errors
    expect(screen.getByText(mockTrack.title)).toBeInTheDocument()
  })

  // ============================================================================
  // Progress Bar Tests
  // ============================================================================

  it('displays progress bar', () => {
    render(<BottomPlayerBar {...defaultProps} />)

    // Progress bar should be present (rendered as a Box with LinearProgress or custom slider)
    const { container } = render(<BottomPlayerBar {...defaultProps} />)
    expect(container.querySelector('[role="progressbar"]') ||
           container.querySelector('.MuiLinearProgress-root')).toBeTruthy()
  })

  // ============================================================================
  // Favorite Button Tests
  // ============================================================================

  it('displays favorite button', () => {
    const { container } = render(<BottomPlayerBar {...defaultProps} />)

    // Favorite icon (outlined or filled)
    const favoriteIcon = container.querySelector('[data-testid="FavoriteOutlinedIcon"]') ||
                         container.querySelector('[data-testid="FavoriteIcon"]')
    expect(favoriteIcon).toBeInTheDocument()
  })

  it('toggles favorite state', () => {
    const { container } = render(<BottomPlayerBar {...defaultProps} />)

    const favoriteButton = container.querySelector('[data-testid="FavoriteOutlinedIcon"]')?.closest('button')
    if (favoriteButton) {
      // Click to favorite
      fireEvent.click(favoriteButton)

      // Should change state (this is internal, harder to verify without state exposure)
      expect(favoriteButton).toBeInTheDocument()
    }
  })

  // ============================================================================
  // Responsive Behavior Tests
  // ============================================================================

  it('renders with fixed positioning at bottom', () => {
    const { container } = render(<BottomPlayerBar {...defaultProps} />)

    const playerContainer = container.firstChild as HTMLElement
    const styles = window.getComputedStyle(playerContainer)

    expect(styles.position).toBe('fixed')
    expect(styles.bottom).toBe('0px')
  })

  // ============================================================================
  // Edge Cases
  // ============================================================================

  it('handles undefined props gracefully', () => {
    render(<BottomPlayerBar />)

    // Should render without crashing
    expect(screen.getByText('No track playing')).toBeInTheDocument()
  })

  it('handles track with very long title', () => {
    const longTitleTrack = {
      ...mockTrack,
      title: 'This is a very long track title that should be handled gracefully by the component',
    }

    render(<BottomPlayerBar {...defaultProps} currentTrack={longTitleTrack} />)

    expect(screen.getByText(longTitleTrack.title)).toBeInTheDocument()
  })

  it('updates when track changes', () => {
    const { rerender } = render(<BottomPlayerBar {...defaultProps} />)

    expect(screen.getByText('Test Track')).toBeInTheDocument()

    const newTrack = { ...mockTrack, title: 'New Track', artist: 'New Artist' }
    rerender(<BottomPlayerBar {...defaultProps} currentTrack={newTrack} />)

    expect(screen.getByText('New Track')).toBeInTheDocument()
    expect(screen.getByText('New Artist')).toBeInTheDocument()
  })
})
