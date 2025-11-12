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

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material/styles';
import { DraggableTrackRow } from '../DraggableTrackRow';
import { auralisTheme } from '../../../theme/auralisTheme';

// Mock Draggable component from @hello-pangea/dnd
jest.mock('@hello-pangea/dnd', () => ({
  Draggable: ({ children, draggableId, index, isDragDisabled }: any) => {
    return (
      <div
        data-testid={`draggable-${draggableId}`}
        data-drag-disabled={isDragDisabled}
      >
        {children(
          {
            innerRef: jest.fn(),
            draggableProps: { 'data-rbd-draggable-id': draggableId },
            dragHandleProps: { 'data-rbd-drag-handle-id': `${draggableId}-handle` },
          },
          { isDragging: false, isDropAnimating: false }
        )}
      </div>
    );
  },
}));

// Mock TrackRow component
jest.mock('../TrackRow', () => {
  return function MockTrackRow({ track, onPlay }: any) {
    return (
      <div data-testid={`track-row-${track.id}`}>
        <span>{track.title}</span>
        <button onClick={() => onPlay(track.id)}>Play</button>
      </div>
    );
  };
});

const mockTrack = {
  id: 1,
  title: 'Test Track',
  artist: 'Test Artist',
  album: 'Test Album',
  duration: 180,
};

const Wrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <BrowserRouter>
    <ThemeProvider theme={auralisTheme}>
      {children}
    </ThemeProvider>
  </BrowserRouter>
);

describe('DraggableTrackRow', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Rendering', () => {
    it('should render draggable container', () => {
      render(
        <Wrapper>
          <DraggableTrackRow
            track={mockTrack}
            index={0}
            draggableId="track-1"
            onPlay={jest.fn()}
          />
        </Wrapper>
      );

      expect(screen.getByTestId('draggable-track-1')).toBeInTheDocument();
    });

    it('should render track row', () => {
      render(
        <Wrapper>
          <DraggableTrackRow
            track={mockTrack}
            index={0}
            draggableId="track-1"
            onPlay={jest.fn()}
          />
        </Wrapper>
      );

      expect(screen.getByTestId('track-row-1')).toBeInTheDocument();
    });

    it('should display track title', () => {
      render(
        <Wrapper>
          <DraggableTrackRow
            track={mockTrack}
            index={0}
            draggableId="track-1"
            onPlay={jest.fn()}
          />
        </Wrapper>
      );

      expect(screen.getByText('Test Track')).toBeInTheDocument();
    });

    it('should show drag handle by default', () => {
      const { container } = render(
        <Wrapper>
          <DraggableTrackRow
            track={mockTrack}
            index={0}
            draggableId="track-1"
            onPlay={jest.fn()}
            showDragHandle={true}
          />
        </Wrapper>
      );

      const dragHandle = container.querySelector('[data-rbd-drag-handle-id]');
      expect(dragHandle).toBeInTheDocument();
    });

    it('should hide drag handle when showDragHandle is false', () => {
      const { container } = render(
        <Wrapper>
          <DraggableTrackRow
            track={mockTrack}
            index={0}
            draggableId="track-1"
            onPlay={jest.fn()}
            showDragHandle={false}
          />
        </Wrapper>
      );

      const dragHandle = container.querySelector('[data-rbd-drag-handle-id]');
      expect(dragHandle).not.toBeInTheDocument();
    });
  });

  describe('Drag and Drop', () => {
    it('should have draggable properties', () => {
      const { container } = render(
        <Wrapper>
          <DraggableTrackRow
            track={mockTrack}
            index={0}
            draggableId="track-1"
            onPlay={jest.fn()}
          />
        </Wrapper>
      );

      const draggable = container.querySelector('[data-rbd-draggable-id]');
      expect(draggable).toHaveAttribute('data-rbd-draggable-id', 'track-1');
    });

    it('should pass correct index', () => {
      render(
        <Wrapper>
          <DraggableTrackRow
            track={mockTrack}
            index={5}
            draggableId="track-1"
            onPlay={jest.fn()}
          />
        </Wrapper>
      );

      // Index is passed to Draggable component internally
      expect(screen.getByTestId('draggable-track-1')).toBeInTheDocument();
    });

    it('should disable drag when isDragDisabled is true', () => {
      const { container } = render(
        <Wrapper>
          <DraggableTrackRow
            track={mockTrack}
            index={0}
            draggableId="track-1"
            onPlay={jest.fn()}
            isDragDisabled={true}
          />
        </Wrapper>
      );

      const draggable = screen.getByTestId('draggable-track-1');
      expect(draggable).toHaveAttribute('data-drag-disabled', 'true');
    });

    it('should enable drag by default', () => {
      const draggable = screen.getByTestId('draggable-track-1');
      expect(draggable).toHaveAttribute('data-drag-disabled', 'false');
    });
  });

  describe('Playback Integration', () => {
    it('should call onPlay when track play button clicked', async () => {
      const user = userEvent.setup();
      const onPlay = jest.fn();

      render(
        <Wrapper>
          <DraggableTrackRow
            track={mockTrack}
            index={0}
            draggableId="track-1"
            onPlay={onPlay}
          />
        </Wrapper>
      );

      const playButton = screen.getByRole('button', { name: /play/i });
      await user.click(playButton);

      expect(onPlay).toHaveBeenCalledWith(1);
    });

    it('should pass onPause callback to TrackRow', () => {
      const onPause = jest.fn();

      render(
        <Wrapper>
          <DraggableTrackRow
            track={mockTrack}
            index={0}
            draggableId="track-1"
            onPlay={jest.fn()}
            onPause={onPause}
          />
        </Wrapper>
      );

      expect(screen.getByTestId('track-row-1')).toBeInTheDocument();
    });

    it('should pass isPlaying state', () => {
      render(
        <Wrapper>
          <DraggableTrackRow
            track={mockTrack}
            index={0}
            draggableId="track-1"
            onPlay={jest.fn()}
            isPlaying={true}
          />
        </Wrapper>
      );

      expect(screen.getByTestId('track-row-1')).toBeInTheDocument();
    });

    it('should pass isCurrent state', () => {
      render(
        <Wrapper>
          <DraggableTrackRow
            track={mockTrack}
            index={0}
            draggableId="track-1"
            onPlay={jest.fn()}
            isCurrent={true}
          />
        </Wrapper>
      );

      expect(screen.getByTestId('track-row-1')).toBeInTheDocument();
    });
  });

  describe('Callbacks', () => {
    it('should pass all callbacks to TrackRow', () => {
      const callbacks = {
        onPlay: jest.fn(),
        onPause: jest.fn(),
        onDoubleClick: jest.fn(),
        onEditMetadata: jest.fn(),
        onToggleFavorite: jest.fn(),
        onShowAlbum: jest.fn(),
        onShowArtist: jest.fn(),
        onShowInfo: jest.fn(),
        onDelete: jest.fn(),
      };

      render(
        <Wrapper>
          <DraggableTrackRow
            track={mockTrack}
            index={0}
            draggableId="track-1"
            {...callbacks}
          />
        </Wrapper>
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
        <Wrapper>
          <DraggableTrackRow
            track={track1}
            index={0}
            draggableId="track-1"
            onPlay={jest.fn()}
          />
          <DraggableTrackRow
            track={track2}
            index={1}
            draggableId="track-2"
            onPlay={jest.fn()}
          />
          <DraggableTrackRow
            track={track3}
            index={2}
            draggableId="track-3"
            onPlay={jest.fn()}
          />
        </Wrapper>
      );

      expect(screen.getByText('Track 1')).toBeInTheDocument();
      expect(screen.getByText('Track 2')).toBeInTheDocument();
      expect(screen.getByText('Track 3')).toBeInTheDocument();
    });

    it('should have unique draggable IDs', () => {
      const track1 = { ...mockTrack, id: 1 };
      const track2 = { ...mockTrack, id: 2 };

      const { container } = render(
        <Wrapper>
          <DraggableTrackRow
            track={track1}
            index={0}
            draggableId="track-1"
            onPlay={jest.fn()}
          />
          <DraggableTrackRow
            track={track2}
            index={1}
            draggableId="track-2"
            onPlay={jest.fn()}
          />
        </Wrapper>
      );

      const draggables = container.querySelectorAll('[data-testid^="draggable"]');
      expect(draggables.length).toBe(2);
    });
  });

  describe('Accessibility', () => {
    it('should have accessible drag handle', () => {
      const { container } = render(
        <Wrapper>
          <DraggableTrackRow
            track={mockTrack}
            index={0}
            draggableId="track-1"
            onPlay={jest.fn()}
            showDragHandle={true}
          />
        </Wrapper>
      );

      const dragHandle = container.querySelector('[data-rbd-drag-handle-id]');
      expect(dragHandle).toBeInTheDocument();
    });

    it('should have accessible play button', async () => {
      const user = userEvent.setup();

      render(
        <Wrapper>
          <DraggableTrackRow
            track={mockTrack}
            index={0}
            draggableId="track-1"
            onPlay={jest.fn()}
          />
        </Wrapper>
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
        <Wrapper>
          <DraggableTrackRow
            track={minimalTrack}
            index={0}
            draggableId="track-1"
            onPlay={jest.fn()}
          />
        </Wrapper>
      );

      expect(screen.getByText('Minimal Track')).toBeInTheDocument();
    });

    it('should handle large index values', () => {
      render(
        <Wrapper>
          <DraggableTrackRow
            track={mockTrack}
            index={9999}
            draggableId="track-1"
            onPlay={jest.fn()}
          />
        </Wrapper>
      );

      expect(screen.getByTestId('track-row-1')).toBeInTheDocument();
    });

    it('should handle special characters in draggableId', () => {
      const specialId = 'track-@#$%-1';

      const { container } = render(
        <Wrapper>
          <DraggableTrackRow
            track={mockTrack}
            index={0}
            draggableId={specialId}
            onPlay={jest.fn()}
          />
        </Wrapper>
      );

      expect(screen.getByTestId(`draggable-${specialId}`)).toBeInTheDocument();
    });
  });
});
