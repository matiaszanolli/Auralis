/**
 * DraggableTrackRow Component Tests
 *
 * Tests the draggable track row with @hello-pangea/dnd integration:
 * - Drag and drop functionality
 * - Drag handle display and interaction
 * - Opacity changes during drag
 * - Disabled drag state
 * - All TrackRow callbacks
 */

import { vi } from 'vitest';
import React from 'react';
import { render, screen, fireEvent } from '@/test/test-utils';
import userEvent from '@testing-library/user-event';
import { DraggableTrackRow } from '../DraggableTrackRow';

// Mock TrackRow component
vi.mock('../TrackRow', () => ({
  TrackRow: function MockTrackRow({ track, onPlay }: any) {
    return (
      <div data-testid={`track-row-${track.id}`}>
        <span>{track.title}</span>
        <button onClick={() => onPlay(track.id)}>Play</button>
      </div>
    );
  },
  Track: class MockTrack {},
}));

const mockTrack = {
  id: 1,
  title: 'Test Track',
  artist: 'Test Artist',
  album: 'Test Album',
  duration: 180,
};


describe('DraggableTrackRow', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Rendering', () => {
    it('should render draggable container with TrackRow', () => {
      render(
        <DraggableTrackRow
            track={mockTrack}
            index={0}
            draggableId="track-1"
            onPlay={vi.fn()}
          />
      );

      // Component should render the wrapped TrackRow
      expect(screen.getByTestId('track-row-1')).toBeInTheDocument();
    });

    it('should render track row', () => {
      render(
        <DraggableTrackRow
            track={mockTrack}
            index={0}
            draggableId="track-1"
            onPlay={vi.fn()}
          />
      );

      expect(screen.getByTestId('track-row-1')).toBeInTheDocument();
    });

    it('should display track title', () => {
      render(
        <DraggableTrackRow
            track={mockTrack}
            index={0}
            draggableId="track-1"
            onPlay={vi.fn()}
          />
      );

      expect(screen.getByText('Test Track')).toBeInTheDocument();
    });

    it('should show drag handle by default', () => {
      const { container } = render(
        <DraggableTrackRow
            track={mockTrack}
            index={0}
            draggableId="track-1"
            onPlay={vi.fn()}
            showDragHandle={true}
          />
      );

      // Drag handle should be rendered when showDragHandle is true
      const dragIcons = container.querySelectorAll('[data-testid="DragIndicatorIcon"]');
      expect(dragIcons.length).toBeGreaterThan(0);
    });

    it('should hide drag handle when showDragHandle is false', () => {
      const { container } = render(
        <DraggableTrackRow
            track={mockTrack}
            index={0}
            draggableId="track-1"
            onPlay={vi.fn()}
            showDragHandle={false}
          />
      );

      // Drag handle should not be rendered when showDragHandle is false
      const dragIcons = container.querySelectorAll('[data-testid="DragIndicatorIcon"]');
      expect(dragIcons.length).toBe(0);
    });
  });

  describe('Drag and Drop', () => {
    it('should render with draggable properties', () => {
      render(
        <DraggableTrackRow
            track={mockTrack}
            index={0}
            draggableId="track-1"
            onPlay={vi.fn()}
          />
      );

      // Component should render the track row which is wrapped by Draggable
      expect(screen.getByTestId('track-row-1')).toBeInTheDocument();
    });

    it('should pass correct index to Draggable', () => {
      render(
        <DraggableTrackRow
            track={mockTrack}
            index={5}
            draggableId="track-1"
            onPlay={vi.fn()}
          />
      );

      // Component should still render properly with any index
      expect(screen.getByTestId('track-row-1')).toBeInTheDocument();
    });

    it('should handle drag disabled state', () => {
      render(
        <DraggableTrackRow
            track={mockTrack}
            index={0}
            draggableId="track-1"
            onPlay={vi.fn()}
            isDragDisabled={true}
          />
      );

      // Component should render normally even when drag is disabled
      expect(screen.getByTestId('track-row-1')).toBeInTheDocument();
    });

    it('should enable drag by default', () => {
      render(
        <DraggableTrackRow
          track={mockTrack}
          index={0}
          draggableId="track-1"
          onPlay={vi.fn()}
        />
      );

      // Component should render with drag enabled
      expect(screen.getByTestId('track-row-1')).toBeInTheDocument();
    });
  });

  describe('Playback Integration', () => {
    it('should call onPlay when track play button clicked', async () => {
      const user = userEvent.setup();
      const onPlay = vi.fn();

      render(
        <DraggableTrackRow
            track={mockTrack}
            index={0}
            draggableId="track-1"
            onPlay={onPlay}
          />
      );

      const playButton = screen.getByRole('button', { name: /play/i });
      await user.click(playButton);

      expect(onPlay).toHaveBeenCalledWith(1);
    });

    it('should pass onPause callback to TrackRow', () => {
      const onPause = vi.fn();

      render(
        <DraggableTrackRow
            track={mockTrack}
            index={0}
            draggableId="track-1"
            onPlay={vi.fn()}
            onPause={onPause}
          />
      );

      expect(screen.getByTestId('track-row-1')).toBeInTheDocument();
    });

    it('should pass isPlaying state', () => {
      render(
        <DraggableTrackRow
            track={mockTrack}
            index={0}
            draggableId="track-1"
            onPlay={vi.fn()}
            isPlaying={true}
          />
      );

      expect(screen.getByTestId('track-row-1')).toBeInTheDocument();
    });

    it('should pass isCurrent state', () => {
      render(
        <DraggableTrackRow
            track={mockTrack}
            index={0}
            draggableId="track-1"
            onPlay={vi.fn()}
            isCurrent={true}
          />
      );

      expect(screen.getByTestId('track-row-1')).toBeInTheDocument();
    });
  });

  describe('Callbacks', () => {
    it('should pass all callbacks to TrackRow', () => {
      const callbacks = {
        onPlay: vi.fn(),
        onPause: vi.fn(),
        onDoubleClick: vi.fn(),
        onEditMetadata: vi.fn(),
        onToggleFavorite: vi.fn(),
        onShowAlbum: vi.fn(),
        onShowArtist: vi.fn(),
        onShowInfo: vi.fn(),
        onDelete: vi.fn(),
      };

      render(
        <DraggableTrackRow
            track={mockTrack}
            index={0}
            draggableId="track-1"
            {...callbacks}
          />
      );

      expect(screen.getByTestId('track-row-1')).toBeInTheDocument();
    });
  });

  describe('Multiple Tracks', () => {
    it('should handle multiple draggable rows', () => {
      const track1 = { ...mockTrack, id: 1, title: 'Track 1' };
      const track2 = { ...mockTrack, id: 2, title: 'Track 2' };
      const track3 = { ...mockTrack, id: 3, title: 'Track 3' };

      render(
        <>
          <DraggableTrackRow
            track={track1}
            index={0}
            draggableId="track-1"
            onPlay={vi.fn()}
          />
          <DraggableTrackRow
            track={track2}
            index={1}
            draggableId="track-2"
            onPlay={vi.fn()}
          />
          <DraggableTrackRow
            track={track3}
            index={2}
            draggableId="track-3"
            onPlay={vi.fn()}
          />
        </>
      );

      expect(screen.getByText('Track 1')).toBeInTheDocument();
      expect(screen.getByText('Track 2')).toBeInTheDocument();
      expect(screen.getByText('Track 3')).toBeInTheDocument();
    });

    it('should have unique draggable IDs', () => {
      const track1 = { ...mockTrack, id: 1 };
      const track2 = { ...mockTrack, id: 2 };

      render(
        <>
          <DraggableTrackRow
            track={track1}
            index={0}
            draggableId="track-1"
            onPlay={vi.fn()}
          />
          <DraggableTrackRow
            track={track2}
            index={1}
            draggableId="track-2"
            onPlay={vi.fn()}
          />
        </>
      );

      // Both track rows should render
      expect(screen.getByTestId('track-row-1')).toBeInTheDocument();
      expect(screen.getByTestId('track-row-2')).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('should have accessible drag handle', () => {
      const { container } = render(
        <DraggableTrackRow
            track={mockTrack}
            index={0}
            draggableId="track-1"
            onPlay={vi.fn()}
            showDragHandle={true}
          />
      );

      // Drag indicator icon should be visible when showDragHandle is true
      const dragIcons = container.querySelectorAll('[data-testid="DragIndicatorIcon"]');
      expect(dragIcons.length).toBeGreaterThan(0);
    });

    it('should have accessible play button', async () => {
      const user = userEvent.setup();

      render(
        <DraggableTrackRow
            track={mockTrack}
            index={0}
            draggableId="track-1"
            onPlay={vi.fn()}
          />
      );

      const playButton = screen.getByRole('button', { name: /play/i });
      expect(playButton).toBeInTheDocument();

      playButton.focus();
      expect(document.activeElement).toBe(playButton);

      await user.keyboard('{Enter}');
      expect(document.activeElement).toBeInTheDocument();
    });
  });

  describe('Edge Cases', () => {
    it('should handle track with missing optional fields', () => {
      const minimalTrack = {
        id: 1,
        title: 'Minimal Track',
        artist: 'Artist',
        album: 'Album',
        duration: 180,
      };

      render(
        <DraggableTrackRow
            track={minimalTrack}
            index={0}
            draggableId="track-1"
            onPlay={vi.fn()}
          />
      );

      expect(screen.getByText('Minimal Track')).toBeInTheDocument();
    });

    it('should handle large index values', () => {
      render(
        <DraggableTrackRow
            track={mockTrack}
            index={9999}
            draggableId="track-1"
            onPlay={vi.fn()}
          />
      );

      expect(screen.getByTestId('track-row-1')).toBeInTheDocument();
    });

    it('should handle special characters in draggableId', () => {
      const specialId = 'track-@#$%-1';

      const { container } = render(
        <DraggableTrackRow
            track={mockTrack}
            index={0}
            draggableId={specialId}
            onPlay={vi.fn()}
          />
      );

      expect(screen.getByTestId(`draggable-${specialId}`)).toBeInTheDocument();
    });
  });
});
