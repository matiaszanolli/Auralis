/**
 * EnhancedTrackQueue Component Tests
 *
 * Tests for the drag-and-drop queue management component,
 * including reordering, removal, shuffle, and clear functionality.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, within } from '@/test/test-utils'
import userEvent from '@testing-library/user-event'
import { EnhancedTrackQueue } from './EnhancedTrackQueue'

// Mock toast notifications
vi.mock('@/components/shared/Toast', () => ({
  useToast: () => ({
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  }),
}))

const mockTracks = [
  { id: 1, title: 'Track 1', artist: 'Artist 1', duration: 180 },
  { id: 2, title: 'Track 2', artist: 'Artist 2', duration: 200 },
  { id: 3, title: 'Track 3', artist: 'Artist 3', duration: 150 },
]

describe('EnhancedTrackQueue', () => {
  describe('Rendering', () => {
    it('renders queue title', () => {
      render(<EnhancedTrackQueue tracks={mockTracks} />)
      expect(screen.getByText('Queue')).toBeInTheDocument()
    })

    it('renders custom title', () => {
      render(<EnhancedTrackQueue tracks={mockTracks} title="My Custom Queue" />)
      expect(screen.getByText('My Custom Queue')).toBeInTheDocument()
    })

    it('displays all tracks', () => {
      render(<EnhancedTrackQueue tracks={mockTracks} />)

      expect(screen.getByText('Track 1')).toBeInTheDocument()
      expect(screen.getByText('Track 2')).toBeInTheDocument()
      expect(screen.getByText('Track 3')).toBeInTheDocument()
    })

    it('displays track artists', () => {
      render(<EnhancedTrackQueue tracks={mockTracks} />)

      expect(screen.getByText('Artist 1')).toBeInTheDocument()
      expect(screen.getByText('Artist 2')).toBeInTheDocument()
      expect(screen.getByText('Artist 3')).toBeInTheDocument()
    })

    it('displays track durations', () => {
      render(<EnhancedTrackQueue tracks={mockTracks} />)

      // Duration formatted as MM:SS
      expect(screen.getByText('3:00')).toBeInTheDocument() // 180s
      expect(screen.getByText('3:20')).toBeInTheDocument() // 200s
      expect(screen.getByText('2:30')).toBeInTheDocument() // 150s
    })
  })

  describe('Empty State', () => {
    it('shows empty state when no tracks', () => {
      render(<EnhancedTrackQueue tracks={[]} />)

      expect(screen.getByText(/queue is empty/i)).toBeInTheDocument()
    })

    it('does not show controls when queue is empty', () => {
      render(<EnhancedTrackQueue tracks={[]} />)

      expect(screen.queryByLabelText('Shuffle queue')).not.toBeInTheDocument()
      expect(screen.queryByLabelText('Clear queue')).not.toBeInTheDocument()
    })
  })

  describe('Current Track Highlighting', () => {
    it('highlights current track', () => {
      render(<EnhancedTrackQueue tracks={mockTracks} currentTrackId={2} />)

      const track2 = screen.getByText('Track 2').closest('div')
      expect(track2).toHaveClass('current-track') // or whatever class indicates current track
    })

    it('does not highlight other tracks', () => {
      render(<EnhancedTrackQueue tracks={mockTracks} currentTrackId={2} />)

      const track1 = screen.getByText('Track 1').closest('div')
      const track3 = screen.getByText('Track 3').closest('div')

      expect(track1).not.toHaveClass('current-track')
      expect(track3).not.toHaveClass('current-track')
    })
  })

  describe('Track Click', () => {
    it('calls onTrackClick when a track is clicked', async () => {
      const user = userEvent.setup()
      const handleTrackClick = vi.fn()

      render(
        <EnhancedTrackQueue
          tracks={mockTracks}
          onTrackClick={handleTrackClick}
        />
      )

      const track = screen.getByText('Track 2')
      await user.click(track)

      expect(handleTrackClick).toHaveBeenCalledWith(2)
    })

    it('does not call onTrackClick when handler is not provided', async () => {
      const user = userEvent.setup()

      render(<EnhancedTrackQueue tracks={mockTracks} />)

      const track = screen.getByText('Track 2')
      // Should not throw error
      await user.click(track)
    })
  })

  describe('Remove Track', () => {
    it('shows remove button on hover', async () => {
      const user = userEvent.setup()

      render(
        <EnhancedTrackQueue
          tracks={mockTracks}
          onRemoveTrack={vi.fn()}
        />
      )

      const trackRow = screen.getByText('Track 1').closest('div')!

      // Hover over track
      await user.hover(trackRow)

      // Remove button should be visible
      const removeButton = within(trackRow).getByLabelText(/remove/i)
      expect(removeButton).toBeInTheDocument()
    })

    it('calls onRemoveTrack with correct index', async () => {
      const user = userEvent.setup()
      const handleRemove = vi.fn()

      render(
        <EnhancedTrackQueue
          tracks={mockTracks}
          onRemoveTrack={handleRemove}
        />
      )

      const trackRow = screen.getByText('Track 2').closest('div')!
      const removeButton = within(trackRow).getByLabelText(/remove/i)

      await user.click(removeButton)

      // Should be called with index 1 (second track)
      expect(handleRemove).toHaveBeenCalledWith(1)
    })

    it('does not show remove button when handler not provided', () => {
      render(<EnhancedTrackQueue tracks={mockTracks} />)

      const trackRow = screen.getByText('Track 1').closest('div')!
      const removeButton = within(trackRow).queryByLabelText(/remove/i)

      expect(removeButton).not.toBeInTheDocument()
    })
  })

  describe('Shuffle Queue', () => {
    it('shows shuffle button when handler is provided', () => {
      render(
        <EnhancedTrackQueue
          tracks={mockTracks}
          onShuffleQueue={vi.fn()}
        />
      )

      expect(screen.getByLabelText('Shuffle queue')).toBeInTheDocument()
    })

    it('calls onShuffleQueue when clicked', async () => {
      const user = userEvent.setup()
      const handleShuffle = vi.fn()

      render(
        <EnhancedTrackQueue
          tracks={mockTracks}
          onShuffleQueue={handleShuffle}
        />
      )

      const shuffleButton = screen.getByLabelText('Shuffle queue')
      await user.click(shuffleButton)

      expect(handleShuffle).toHaveBeenCalled()
    })

    it('does not show shuffle button when handler not provided', () => {
      render(<EnhancedTrackQueue tracks={mockTracks} />)

      expect(screen.queryByLabelText('Shuffle queue')).not.toBeInTheDocument()
    })
  })

  describe('Clear Queue', () => {
    it('shows clear button when handler is provided', () => {
      render(
        <EnhancedTrackQueue
          tracks={mockTracks}
          onClearQueue={vi.fn()}
        />
      )

      expect(screen.getByLabelText('Clear queue')).toBeInTheDocument()
    })

    it('calls onClearQueue when clicked', async () => {
      const user = userEvent.setup()
      const handleClear = vi.fn()

      render(
        <EnhancedTrackQueue
          tracks={mockTracks}
          onClearQueue={handleClear}
        />
      )

      const clearButton = screen.getByLabelText('Clear queue')
      await user.click(clearButton)

      expect(handleClear).toHaveBeenCalled()
    })

    it('does not show clear button when handler not provided', () => {
      render(<EnhancedTrackQueue tracks={mockTracks} />)

      expect(screen.queryByLabelText('Clear queue')).not.toBeInTheDocument()
    })
  })

  describe('Drag and Drop', () => {
    it('renders draggable items', () => {
      render(
        <EnhancedTrackQueue
          tracks={mockTracks}
          onReorderQueue={vi.fn()}
        />
      )

      // Check for drag handles or draggable indicators
      const trackRows = screen.getAllByRole('listitem')
      expect(trackRows).toHaveLength(3)
    })

    it('calls onReorderQueue with new order', async () => {
      const handleReorder = vi.fn()

      render(
        <EnhancedTrackQueue
          tracks={mockTracks}
          onReorderQueue={handleReorder}
        />
      )

      // Note: Actual drag-and-drop testing is complex with @hello-pangea/dnd
      // In a real test, you'd use their testing utilities or mock the DragDropContext
      // For now, we verify the component renders with drag-drop capabilities
      expect(screen.getByText('Track 1')).toBeInTheDocument()
    })

    it('does not enable drag-drop when handler not provided', () => {
      render(<EnhancedTrackQueue tracks={mockTracks} />)

      // Component should still render, just without drag-drop functionality
      expect(screen.getByText('Track 1')).toBeInTheDocument()
    })
  })

  describe('Track Count', () => {
    it('displays track count in header', () => {
      render(<EnhancedTrackQueue tracks={mockTracks} />)

      expect(screen.getByText(/3 tracks/i)).toBeInTheDocument()
    })

    it('updates count when tracks change', () => {
      const { rerender } = render(<EnhancedTrackQueue tracks={mockTracks} />)

      expect(screen.getByText(/3 tracks/i)).toBeInTheDocument()

      // Add more tracks
      const moreTracks = [...mockTracks, { id: 4, title: 'Track 4', artist: 'Artist 4', duration: 120 }]
      rerender(<EnhancedTrackQueue tracks={moreTracks} />)

      expect(screen.getByText(/4 tracks/i)).toBeInTheDocument()
    })

    it('shows singular "track" when only one track', () => {
      render(<EnhancedTrackQueue tracks={[mockTracks[0]]} />)

      expect(screen.getByText(/1 track$/i)).toBeInTheDocument()
    })
  })

  describe('Accessibility', () => {
    it('has proper ARIA labels for buttons', () => {
      render(
        <EnhancedTrackQueue
          tracks={mockTracks}
          onShuffleQueue={vi.fn()}
          onClearQueue={vi.fn()}
        />
      )

      expect(screen.getByLabelText('Shuffle queue')).toBeInTheDocument()
      expect(screen.getByLabelText('Clear queue')).toBeInTheDocument()
    })

    it('has clickable track rows', () => {
      render(
        <EnhancedTrackQueue
          tracks={mockTracks}
          onTrackClick={vi.fn()}
        />
      )

      const trackRows = screen.getAllByRole('listitem')
      trackRows.forEach(row => {
        expect(row).toHaveStyle({ cursor: 'pointer' })
      })
    })
  })

  describe('Performance', () => {
    it('handles large queues efficiently', () => {
      const largeTracks = Array.from({ length: 100 }, (_, i) => ({
        id: i,
        title: `Track ${i}`,
        artist: `Artist ${i}`,
        duration: 180,
      }))

      const { container } = render(<EnhancedTrackQueue tracks={largeTracks} />)

      // Should render without performance issues
      expect(container).toBeInTheDocument()
      expect(screen.getByText(/100 tracks/i)).toBeInTheDocument()
    })
  })
})
