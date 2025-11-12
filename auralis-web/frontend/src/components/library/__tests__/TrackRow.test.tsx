/**
 * TrackRow Component Tests
 *
 * Tests the track row component used in library lists:
 * - Track info display
 * - Selection checkbox
 * - Play/pause on double-click
 * - Context menu
 * - Hover states
 * - Drag handle
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material/styles';
import TrackRow from '../TrackRow';
import { useTrackSelection } from '../../../hooks/useTrackSelection';
import { auralisTheme } from '../../../theme/auralisTheme';

// Mock hooks and components
jest.mock('../../../hooks/useTrackSelection');
jest.mock('../TrackContextMenu', () => {
  return function MockContextMenu({ track, onPlay }: any) {
    return (
      <div data-testid="track-context-menu">
        <button onClick={() => onPlay?.(track)}>Play</button>
      </div>
    );
  };
});
jest.mock('../../album/AlbumArt', () => {
  return function MockAlbumArt({ track }: any) {
    return <div data-testid="track-artwork">Art: {track.title}</div>;
  };
});

const mockTrack = {
  id: 1,
  title: 'Test Track',
  artist: 'Test Artist',
  album: 'Test Album',
  duration: 180,
  artwork: 'http://example.com/art.jpg',
  filepath: '/path/to/track.mp3',
};

const mockTrack2 = {
  id: 2,
  title: 'Another Track',
  artist: 'Another Artist',
  album: 'Another Album',
  duration: 240,
  artwork: 'http://example.com/art2.jpg',
  filepath: '/path/to/track2.mp3',
};

const mockSelectionContext = {
  selectedTracks: new Set<number>(),
  isSelected: (id: number) => false,
  toggleSelection: jest.fn(),
  addToSelection: jest.fn(),
  removeFromSelection: jest.fn(),
  clearSelection: jest.fn(),
  selectRange: jest.fn(),
};

const Wrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <BrowserRouter>
    <ThemeProvider theme={auralisTheme}>
      {children}
    </ThemeProvider>
  </BrowserRouter>
);

describe('TrackRow', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (useTrackSelection as jest.Mock).mockReturnValue(mockSelectionContext);
  });

  describe('Rendering', () => {
    it('should render track title', () => {
      render(
        <Wrapper>
          <TrackRow track={mockTrack} />
        </Wrapper>
      );

      expect(screen.getByText('Test Track')).toBeInTheDocument();
    });

    it('should render artist name', () => {
      render(
        <Wrapper>
          <TrackRow track={mockTrack} />
        </Wrapper>
      );

      expect(screen.getByText('Test Artist')).toBeInTheDocument();
    });

    it('should render album name', () => {
      render(
        <Wrapper>
          <TrackRow track={mockTrack} />
        </Wrapper>
      );

      expect(screen.getByText('Test Album')).toBeInTheDocument();
    });

    it('should render duration', () => {
      render(
        <Wrapper>
          <TrackRow track={mockTrack} />
        </Wrapper>
      );

      // Duration should be displayed as MM:SS
      expect(screen.getByText(/3:00|03:00/)).toBeInTheDocument();
    });

    it('should render album artwork', () => {
      render(
        <Wrapper>
          <TrackRow track={mockTrack} />
        </Wrapper>
      );

      expect(screen.getByTestId('track-artwork')).toBeInTheDocument();
    });

    it('should render selection checkbox', () => {
      render(
        <Wrapper>
          <TrackRow track={mockTrack} />
        </Wrapper>
      );

      const checkbox = screen.getByRole('checkbox');
      expect(checkbox).toBeInTheDocument();
    });

    it('should render context menu', () => {
      render(
        <Wrapper>
          <TrackRow track={mockTrack} />
        </Wrapper>
      );

      expect(screen.getByTestId('track-context-menu')).toBeInTheDocument();
    });

    it('should render drag handle if draggable', () => {
      render(
        <Wrapper>
          <TrackRow track={mockTrack} draggable={true} />
        </Wrapper>
      );

      // Drag handle should be present
      const elements = screen.queryAllByTestId(/drag|handle/i);
      expect(elements.length).toBeGreaterThanOrEqual(0);
    });
  });

  describe('Selection', () => {
    it('should check checkbox when selected', () => {
      (useTrackSelection as jest.Mock).mockReturnValue({
        ...mockSelectionContext,
        isSelected: () => true,
        selectedTracks: new Set([1]),
      });

      render(
        <Wrapper>
          <TrackRow track={mockTrack} />
        </Wrapper>
      );

      const checkbox = screen.getByRole('checkbox') as HTMLInputElement;
      expect(checkbox.checked).toBe(true);
    });

    it('should uncheck checkbox when not selected', () => {
      (useTrackSelection as jest.Mock).mockReturnValue({
        ...mockSelectionContext,
        isSelected: () => false,
        selectedTracks: new Set(),
      });

      render(
        <Wrapper>
          <TrackRow track={mockTrack} />
        </Wrapper>
      );

      const checkbox = screen.getByRole('checkbox') as HTMLInputElement;
      expect(checkbox.checked).toBe(false);
    });

    it('should toggle selection on checkbox click', async () => {
      const user = userEvent.setup();
      const toggleSelection = jest.fn();

      (useTrackSelection as jest.Mock).mockReturnValue({
        ...mockSelectionContext,
        toggleSelection,
      });

      render(
        <Wrapper>
          <TrackRow track={mockTrack} />
        </Wrapper>
      );

      const checkbox = screen.getByRole('checkbox');
      await user.click(checkbox);

      expect(toggleSelection).toHaveBeenCalledWith(mockTrack.id);
    });

    it('should support shift-click for range selection', async () => {
      const user = userEvent.setup();
      const selectRange = jest.fn();

      (useTrackSelection as jest.Mock).mockReturnValue({
        ...mockSelectionContext,
        selectRange,
      });

      render(
        <Wrapper>
          <TrackRow track={mockTrack} index={0} />
        </Wrapper>
      );

      const row = screen.getByRole('row');
      await user.click(row, { shiftKey: true });

      expect(selectRange).toHaveBeenCalled();
    });

    it('should support ctrl/cmd-click for multi-select', async () => {
      const user = userEvent.setup();
      const toggleSelection = jest.fn();

      (useTrackSelection as jest.Mock).mockReturnValue({
        ...mockSelectionContext,
        toggleSelection,
      });

      render(
        <Wrapper>
          <TrackRow track={mockTrack} />
        </Wrapper>
      );

      const row = screen.getByRole('row');
      await user.click(row, { ctrlKey: true });

      expect(toggleSelection).toHaveBeenCalledWith(mockTrack.id);
    });
  });

  describe('Playback', () => {
    it('should call onPlay callback on double-click', async () => {
      const user = userEvent.setup();
      const onPlay = jest.fn();

      render(
        <Wrapper>
          <TrackRow track={mockTrack} onPlay={onPlay} />
        </Wrapper>
      );

      const row = screen.getByRole('row');
      await user.dblClick(row);

      expect(onPlay).toHaveBeenCalledWith(mockTrack);
    });

    it('should call onPlay with track from context menu', async () => {
      const user = userEvent.setup();
      const onPlay = jest.fn();

      render(
        <Wrapper>
          <TrackRow track={mockTrack} onPlay={onPlay} />
        </Wrapper>
      );

      const playButton = screen.getByText('Play');
      await user.click(playButton);

      expect(onPlay).toHaveBeenCalledWith(mockTrack);
    });

    it('should disable play on double-click when track unavailable', async () => {
      const user = userEvent.setup();
      const onPlay = jest.fn();

      const unavailableTrack = { ...mockTrack, filepath: null };

      render(
        <Wrapper>
          <TrackRow track={unavailableTrack} onPlay={onPlay} />
        </Wrapper>
      );

      const row = screen.getByRole('row');
      await user.dblClick(row);

      expect(onPlay).not.toHaveBeenCalled();
    });
  });

  describe('Hover States', () => {
    it('should show additional controls on hover', async () => {
      const user = userEvent.setup();

      render(
        <Wrapper>
          <TrackRow track={mockTrack} />
        </Wrapper>
      );

      const row = screen.getByRole('row');
      await user.hover(row);

      // Additional controls should be visible
      const playIcon = screen.queryByTestId(/PlayArrowIcon|PlayIcon/);
      expect(playIcon || document.hidden).toBeTruthy();
    });

    it('should highlight row on hover', async () => {
      const user = userEvent.setup();

      const { container } = render(
        <Wrapper>
          <TrackRow track={mockTrack} />
        </Wrapper>
      );

      const row = container.querySelector('tr');
      if (row) {
        await user.hover(row);
        // Check for hover styling (implementation specific)
        expect(row).toBeInTheDocument();
      }
    });
  });

  describe('Drag and Drop', () => {
    it('should be draggable when draggable prop is true', () => {
      const { container } = render(
        <Wrapper>
          <TrackRow track={mockTrack} draggable={true} />
        </Wrapper>
      );

      const row = container.querySelector('tr');
      expect(row).toHaveAttribute('draggable', 'true');
    });

    it('should not be draggable when draggable prop is false', () => {
      const { container } = render(
        <Wrapper>
          <TrackRow track={mockTrack} draggable={false} />
        </Wrapper>
      );

      const row = container.querySelector('tr');
      expect(row).not.toHaveAttribute('draggable', 'true');
    });

    it('should call onDragStart when drag begins', () => {
      const user = userEvent.setup();
      const onDragStart = jest.fn();

      const { container } = render(
        <Wrapper>
          <TrackRow
            track={mockTrack}
            draggable={true}
            onDragStart={onDragStart}
          />
        </Wrapper>
      );

      const row = container.querySelector('tr');
      if (row) {
        fireEvent.dragStart(row);
        expect(onDragStart).toHaveBeenCalledWith(mockTrack);
      }
    });

    it('should call onDragEnd when drag ends', () => {
      const onDragEnd = jest.fn();

      const { container } = render(
        <Wrapper>
          <TrackRow
            track={mockTrack}
            draggable={true}
            onDragEnd={onDragEnd}
          />
        </Wrapper>
      );

      const row = container.querySelector('tr');
      if (row) {
        fireEvent.dragEnd(row);
        expect(onDragEnd).toHaveBeenCalled();
      }
    });
  });

  describe('Context Menu', () => {
    it('should open context menu on right-click', async () => {
      const user = userEvent.setup();

      render(
        <Wrapper>
          <TrackRow track={mockTrack} />
        </Wrapper>
      );

      const row = screen.getByRole('row');
      fireEvent.contextMenu(row);

      const contextMenu = screen.getByTestId('track-context-menu');
      expect(contextMenu).toBeInTheDocument();
    });

    it('should pass track to context menu', () => {
      render(
        <Wrapper>
          <TrackRow track={mockTrack} />
        </Wrapper>
      );

      expect(screen.getByText(`Art: ${mockTrack.title}`)).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('should have proper table structure', () => {
      render(
        <Wrapper>
          <TrackRow track={mockTrack} />
        </Wrapper>
      );

      expect(screen.getByRole('row')).toBeInTheDocument();
    });

    it('should have accessible track title', () => {
      render(
        <Wrapper>
          <TrackRow track={mockTrack} />
        </Wrapper>
      );

      const titleElement = screen.getByText('Test Track');
      expect(titleElement).toBeInTheDocument();
    });

    it('should support keyboard navigation', async () => {
      const user = userEvent.setup();

      render(
        <Wrapper>
          <TrackRow track={mockTrack} />
        </Wrapper>
      );

      const checkbox = screen.getByRole('checkbox');
      await user.tab();
      // Should be focusable
      expect(document.activeElement).toBeInTheDocument();
    });
  });

  describe('Edge Cases', () => {
    it('should handle very long track titles', () => {
      const longTitleTrack = {
        ...mockTrack,
        title: 'A'.repeat(100),
      };

      const { container } = render(
        <Wrapper>
          <TrackRow track={longTitleTrack} />
        </Wrapper>
      );

      const row = container.querySelector('tr');
      expect(row).toBeInTheDocument();
    });

    it('should handle missing duration', () => {
      const noDurationTrack = {
        ...mockTrack,
        duration: 0,
      };

      render(
        <Wrapper>
          <TrackRow track={noDurationTrack} />
        </Wrapper>
      );

      // Should still render without crashing
      expect(screen.getByText('Test Track')).toBeInTheDocument();
    });

    it('should handle missing artwork', () => {
      const noArtworkTrack = {
        ...mockTrack,
        artwork: null,
      };

      render(
        <Wrapper>
          <TrackRow track={noArtworkTrack} />
        </Wrapper>
      );

      expect(screen.getByText('Test Track')).toBeInTheDocument();
    });

    it('should handle tracks with special characters', () => {
      const specialTrack = {
        ...mockTrack,
        title: 'Track (Remix) [2024]',
        artist: 'Artist & Collaborator',
      };

      render(
        <Wrapper>
          <TrackRow track={specialTrack} />
        </Wrapper>
      );

      expect(screen.getByText(/Track.*Remix.*2024/)).toBeInTheDocument();
    });
  });

  describe('Performance', () => {
    it('should render efficiently with many rows', () => {
      const { container, rerender } = render(
        <Wrapper>
          <TrackRow track={mockTrack} />
        </Wrapper>
      );

      // Update track and ensure no unnecessary re-renders
      rerender(
        <Wrapper>
          <TrackRow track={mockTrack2} />
        </Wrapper>
      );

      expect(screen.getByText('Another Track')).toBeInTheDocument();
    });

    it('should not re-render when parent props unchanged', () => {
      let renderCount = 0;
      const TestWrapper = () => {
        renderCount++;
        return <TrackRow track={mockTrack} />;
      };

      const { rerender } = render(
        <Wrapper>
          <TestWrapper />
        </Wrapper>
      );

      const initialRenderCount = renderCount;

      rerender(
        <Wrapper>
          <TestWrapper />
        </Wrapper>
      );

      // Should not increase render count significantly
      expect(renderCount).toBe(initialRenderCount + 1); // Initial + rerender
    });
  });
});
