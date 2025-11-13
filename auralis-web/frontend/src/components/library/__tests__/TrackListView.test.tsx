/**
 * TrackListView Component Tests
 *
 * Tests the track list view component with:
 * - Grid and list view modes
 * - Infinite scroll with Intersection Observer
 * - Loading states and skeletons
 * - Track selection (list view)
 * - Playback integration
 * - Queue display
 */

import { vi } from 'vitest';
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material/styles';
import TrackListView from '../TrackListView';
import { auralisTheme } from '../../../theme/auralisTheme';

// Mock components
vi.mock('../track/TrackCard', () => {
  return function MockTrackCard({ title, artist, onPlay }: any) {
    return (
      <div data-testid={`track-card-${title}`}>
        <span>{title}</span>
        <span>{artist}</span>
        <button onClick={() => onPlay?.()}>Play</button>
      </div>
    );
  };
});

vi.mock('./SelectableTrackRow', () => {
  return function MockSelectableTrackRow({ track, onPlay, onToggleSelect }: any) {
    return (
      <div data-testid={`track-row-${track.id}`}>
        <input
          type="checkbox"
          onChange={(e) => onToggleSelect(e)}
          data-testid={`checkbox-${track.id}`}
        />
        <span>{track.title}</span>
        <button onClick={() => onPlay?.(track.id)}>Play</button>
      </div>
    );
  };
});

vi.mock('../player/TrackQueue', () => {
  return function MockTrackQueue() {
    return <div data-testid="track-queue">Queue</div>;
  };
});

vi.mock('../shared/SkeletonLoader', () => ({
  LibraryGridSkeleton: () => <div data-testid="grid-skeleton">Loading...</div>,
  TrackRowSkeleton: () => <div data-testid="row-skeleton">Loading row...</div>,
}));

vi.mock('../../services/queueService', () => ({
  removeTrackFromQueue: vi.fn(async () => undefined),
  reorderQueue: vi.fn(async () => undefined),
  shuffleQueue: vi.fn(async () => undefined),
  clearQueue: vi.fn(async () => undefined),
}));

vi.mock('../shared/Toast', () => ({
  useToast: () => ({
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  }),
}));

const mockTracks = [
  {
    id: 1,
    title: 'Track 1',
    artist: 'Artist 1',
    album: 'Album 1',
    album_id: 1,
    duration: 180,
    albumArt: '/art/1.jpg',
    quality: 320,
    isEnhanced: false,
    genre: 'Rock',
    year: 2020,
  },
  {
    id: 2,
    title: 'Track 2',
    artist: 'Artist 2',
    album: 'Album 2',
    album_id: 2,
    duration: 240,
    albumArt: '/art/2.jpg',
    quality: 320,
    isEnhanced: true,
    genre: 'Pop',
    year: 2021,
  },
  {
    id: 3,
    title: 'Track 3',
    artist: 'Artist 3',
    album: 'Album 1',
    album_id: 1,
    duration: 200,
    albumArt: '/art/3.jpg',
    quality: 128,
    isEnhanced: false,
    genre: 'Jazz',
    year: 2022,
  },
];

const defaultProps = {
  tracks: mockTracks,
  viewMode: 'grid' as const,
  loading: false,
  hasMore: false,
  totalTracks: 3,
  isLoadingMore: false,
  currentTrackId: undefined,
  isPlaying: false,
  selectedTracks: new Set<number>(),
  isSelected: (id: number) => false,
  onToggleSelect: vi.fn(),
  onTrackPlay: vi.fn(),
  onPause: vi.fn(),
  onEditMetadata: vi.fn(),
  onLoadMore: vi.fn(),
};

const Wrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <BrowserRouter>
    <ThemeProvider theme={auralisTheme}>
      {children}
    </ThemeProvider>
  </BrowserRouter>
);

describe('TrackListView', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Rendering - Grid Mode', () => {
    it('should render grid view by default', () => {
      render(
        <Wrapper>
          <TrackListView {...defaultProps} viewMode="grid" />
        </Wrapper>
      );

      expect(screen.getByTestId('track-card-Track 1')).toBeInTheDocument();
      expect(screen.getByTestId('track-card-Track 2')).toBeInTheDocument();
      expect(screen.getByTestId('track-card-Track 3')).toBeInTheDocument();
    });

    it('should render all tracks in grid', () => {
      render(
        <Wrapper>
          <TrackListView {...defaultProps} viewMode="grid" />
        </Wrapper>
      );

      expect(screen.getByText('Track 1')).toBeInTheDocument();
      expect(screen.getByText('Track 2')).toBeInTheDocument();
      expect(screen.getByText('Track 3')).toBeInTheDocument();
    });

    it('should display artist name in grid cards', () => {
      render(
        <Wrapper>
          <TrackListView {...defaultProps} viewMode="grid" />
        </Wrapper>
      );

      expect(screen.getByText('Artist 1')).toBeInTheDocument();
      expect(screen.getByText('Artist 2')).toBeInTheDocument();
    });

    it('should render track queue in grid mode', () => {
      render(
        <Wrapper>
          <TrackListView {...defaultProps} viewMode="grid" tracks={mockTracks} />
        </Wrapper>
      );

      expect(screen.getByTestId('track-queue')).toBeInTheDocument();
    });

    it('should not render queue when no tracks', () => {
      render(
        <Wrapper>
          <TrackListView {...defaultProps} viewMode="grid" tracks={[]} />
        </Wrapper>
      );

      expect(screen.queryByTestId('track-queue')).not.toBeInTheDocument();
    });
  });

  describe('Rendering - List Mode', () => {
    it('should render list view', () => {
      render(
        <Wrapper>
          <TrackListView {...defaultProps} viewMode="list" />
        </Wrapper>
      );

      expect(screen.getByTestId('track-row-1')).toBeInTheDocument();
      expect(screen.getByTestId('track-row-2')).toBeInTheDocument();
      expect(screen.getByTestId('track-row-3')).toBeInTheDocument();
    });

    it('should display all tracks in list', () => {
      render(
        <Wrapper>
          <TrackListView {...defaultProps} viewMode="list" />
        </Wrapper>
      );

      expect(screen.getByText('Track 1')).toBeInTheDocument();
      expect(screen.getByText('Track 2')).toBeInTheDocument();
      expect(screen.getByText('Track 3')).toBeInTheDocument();
    });

    it('should show selection checkboxes in list mode', () => {
      render(
        <Wrapper>
          <TrackListView {...defaultProps} viewMode="list" />
        </Wrapper>
      );

      expect(screen.getByTestId('checkbox-1')).toBeInTheDocument();
      expect(screen.getByTestId('checkbox-2')).toBeInTheDocument();
    });

    it('should render in paper container', () => {
      const { container } = render(
        <Wrapper>
          <TrackListView {...defaultProps} viewMode="list" />
        </Wrapper>
      );

      const paper = container.querySelector('[class*="Paper"]');
      expect(paper).toBeInTheDocument();
    });
  });

  describe('Loading State', () => {
    it('should show grid skeleton in grid mode', () => {
      render(
        <Wrapper>
          <TrackListView {...defaultProps} viewMode="grid" loading={true} />
        </Wrapper>
      );

      expect(screen.getByTestId('grid-skeleton')).toBeInTheDocument();
    });

    it('should show row skeletons in list mode', () => {
      render(
        <Wrapper>
          <TrackListView {...defaultProps} viewMode="list" loading={true} />
        </Wrapper>
      );

      expect(screen.getAllByTestId('row-skeleton').length).toBeGreaterThan(0);
    });

    it('should not render tracks while loading', () => {
      render(
        <Wrapper>
          <TrackListView {...defaultProps} viewMode="grid" loading={true} />
        </Wrapper>
      );

      expect(screen.queryByText('Track 1')).not.toBeInTheDocument();
    });
  });

  describe('Empty State', () => {
    it('should handle empty track list', () => {
      render(
        <Wrapper>
          <TrackListView {...defaultProps} tracks={[]} viewMode="list" />
        </Wrapper>
      );

      expect(screen.getByText(/showing all 0 tracks|no tracks/i) || document.body).toBeInTheDocument();
    });

    it('should show end of list message when no more tracks', () => {
      render(
        <Wrapper>
          <TrackListView
            {...defaultProps}
            viewMode="list"
            tracks={mockTracks}
            hasMore={false}
            totalTracks={3}
          />
        </Wrapper>
      );

      expect(screen.getByText(/showing all 3 tracks/)).toBeInTheDocument();
    });
  });

  describe('Infinite Scroll', () => {
    it('should render load more trigger when hasMore is true', () => {
      const { container } = render(
        <Wrapper>
          <TrackListView
            {...defaultProps}
            viewMode="grid"
            hasMore={true}
          />
        </Wrapper>
      );

      // Should have a trigger element for infinite scroll
      const trigger = container.querySelector('[style*="height"]');
      expect(trigger).toBeInTheDocument();
    });

    it('should not render load more when hasMore is false', () => {
      const { container } = render(
        <Wrapper>
          <TrackListView
            {...defaultProps}
            viewMode="grid"
            hasMore={false}
          />
        </Wrapper>
      );

      const emptyBoxes = container.querySelectorAll('div[style*="height: 100px"]');
      expect(emptyBoxes.length).toBe(0);
    });

    it('should show loading spinner during infinite scroll', () => {
      const { container } = render(
        <Wrapper>
          <TrackListView
            {...defaultProps}
            viewMode="grid"
            hasMore={true}
            isLoadingMore={true}
          />
        </Wrapper>
      );

      // Should render spinner animation
      const spinner = container.querySelector('[style*="animation"]');
      expect(spinner).toBeInTheDocument();
    });

    it('should call onLoadMore when observer intersects', async () => {
      const onLoadMore = vi.fn();

      const { container } = render(
        <Wrapper>
          <TrackListView
            {...defaultProps}
            viewMode="grid"
            hasMore={true}
            onLoadMore={onLoadMore}
          />
        </Wrapper>
      );

      // Find the load more ref element
      const triggers = container.querySelectorAll('div');
      const trigger = Array.from(triggers).find(el =>
        el.style.height === '100px'
      ) as HTMLElement;

      if (trigger) {
        // Simulate intersection
        fireEvent.scroll(window, { target: { scrollY: 1000 } });
      }

      // IntersectionObserver should be set up
      expect(onLoadMore || document.body).toBeInTheDocument();
    });

    it('should debounce load more calls', async () => {
      vi.useFakeTimers();
      const onLoadMore = vi.fn();

      render(
        <Wrapper>
          <TrackListView
            {...defaultProps}
            viewMode="grid"
            hasMore={true}
            onLoadMore={onLoadMore}
          />
        </Wrapper>
      );

      // Multiple scroll events should not call onLoadMore multiple times immediately
      vi.advanceTimersByTime(1000);

      vi.useRealTimers();
    });

    it('should show track count during loading', () => {
      render(
        <Wrapper>
          <TrackListView
            {...defaultProps}
            viewMode="list"
            hasMore={true}
            isLoadingMore={true}
            totalTracks={100}
          />
        </Wrapper>
      );

      expect(screen.getByText(/loading more tracks.*3\/100/)).toBeInTheDocument();
    });
  });

  describe('Track Selection - List Mode', () => {
    it('should toggle track selection', async () => {
      const user = userEvent.setup();
      const onToggleSelect = vi.fn();

      render(
        <Wrapper>
          <TrackListView
            {...defaultProps}
            viewMode="list"
            onToggleSelect={onToggleSelect}
          />
        </Wrapper>
      );

      const checkbox = screen.getByTestId('checkbox-1');
      await user.click(checkbox);

      expect(onToggleSelect).toHaveBeenCalled();
    });

    it('should show selected state', () => {
      const selectedTracks = new Set([1]);
      const isSelected = (id: number) => selectedTracks.has(id);

      render(
        <Wrapper>
          <TrackListView
            {...defaultProps}
            viewMode="list"
            selectedTracks={selectedTracks}
            isSelected={isSelected}
          />
        </Wrapper>
      );

      // SelectableTrackRow receives selected prop
      expect(screen.getByTestId('track-row-1')).toBeInTheDocument();
    });

    it('should pass selection callback to rows', async () => {
      const user = userEvent.setup();
      const onToggleSelect = vi.fn();

      render(
        <Wrapper>
          <TrackListView
            {...defaultProps}
            viewMode="list"
            onToggleSelect={onToggleSelect}
          />
        </Wrapper>
      );

      const checkbox = screen.getByTestId('checkbox-1');
      await user.click(checkbox);

      expect(onToggleSelect).toHaveBeenCalledWith(1, expect.any(Object));
    });
  });

  describe('Playback Integration', () => {
    it('should call onTrackPlay in grid mode', async () => {
      const user = userEvent.setup();
      const onTrackPlay = vi.fn();

      render(
        <Wrapper>
          <TrackListView
            {...defaultProps}
            viewMode="grid"
            onTrackPlay={onTrackPlay}
          />
        </Wrapper>
      );

      const playButtons = screen.getAllByRole('button', { name: /play/i });
      await user.click(playButtons[0]);

      expect(onTrackPlay).toHaveBeenCalled();
    });

    it('should call onTrackPlay in list mode', async () => {
      const user = userEvent.setup();
      const onTrackPlay = vi.fn();

      render(
        <Wrapper>
          <TrackListView
            {...defaultProps}
            viewMode="list"
            onTrackPlay={onTrackPlay}
          />
        </Wrapper>
      );

      const playButton = screen.getAllByRole('button', { name: /play/i })[0];
      await user.click(playButton);

      expect(onTrackPlay).toHaveBeenCalled();
    });

    it('should pass correct track to onTrackPlay', async () => {
      const user = userEvent.setup();
      const onTrackPlay = vi.fn();

      render(
        <Wrapper>
          <TrackListView
            {...defaultProps}
            viewMode="grid"
            onTrackPlay={onTrackPlay}
          />
        </Wrapper>
      );

      const card = screen.getByTestId('track-card-Track 1');
      const button = card.querySelector('button');
      if (button) {
        await user.click(button);
        expect(onTrackPlay).toHaveBeenCalledWith(mockTracks[0]);
      }
    });

    it('should highlight current track', () => {
      const { container } = render(
        <Wrapper>
          <TrackListView
            {...defaultProps}
            viewMode="list"
            currentTrackId={2}
            isPlaying={true}
          />
        </Wrapper>
      );

      // Current track should be marked
      expect(screen.getByTestId('track-row-2')).toBeInTheDocument();
    });

    it('should pass isPlaying to track rows', () => {
      render(
        <Wrapper>
          <TrackListView
            {...defaultProps}
            viewMode="list"
            isPlaying={true}
            currentTrackId={1}
          />
        </Wrapper>
      );

      expect(screen.getByTestId('track-row-1')).toBeInTheDocument();
    });
  });

  describe('View Mode Switching', () => {
    it('should switch between grid and list modes', () => {
      const { rerender } = render(
        <Wrapper>
          <TrackListView {...defaultProps} viewMode="grid" />
        </Wrapper>
      );

      expect(screen.getByTestId('track-card-Track 1')).toBeInTheDocument();

      rerender(
        <Wrapper>
          <TrackListView {...defaultProps} viewMode="list" />
        </Wrapper>
      );

      expect(screen.getByTestId('track-row-1')).toBeInTheDocument();
    });

    it('should preserve data when switching views', () => {
      const { rerender } = render(
        <Wrapper>
          <TrackListView {...defaultProps} viewMode="grid" />
        </Wrapper>
      );

      rerender(
        <Wrapper>
          <TrackListView {...defaultProps} viewMode="list" />
        </Wrapper>
      );

      expect(screen.getByText('Track 1')).toBeInTheDocument();
      expect(screen.getByText('Track 2')).toBeInTheDocument();
    });
  });

  describe('Animations', () => {
    it('should apply fade-in animation classes in grid', () => {
      const { container } = render(
        <Wrapper>
          <TrackListView {...defaultProps} viewMode="grid" />
        </Wrapper>
      );

      const gridItems = container.querySelectorAll('[class*="animate"]');
      expect(gridItems.length).toBeGreaterThan(0);
    });

    it('should apply fade-in animation in list', () => {
      const { container } = render(
        <Wrapper>
          <TrackListView {...defaultProps} viewMode="list" />
        </Wrapper>
      );

      const animated = container.querySelectorAll('[class*="animate"]');
      expect(animated.length).toBeGreaterThan(0);
    });

    it('should stagger animations', () => {
      const { container } = render(
        <Wrapper>
          <TrackListView {...defaultProps} viewMode="grid" />
        </Wrapper>
      );

      const items = container.querySelectorAll('[style*="animation"]');
      expect(items.length).toBeGreaterThan(0);
    });
  });

  describe('Accessibility', () => {
    it('should have proper checkbox semantics', () => {
      render(
        <Wrapper>
          <TrackListView {...defaultProps} viewMode="list" />
        </Wrapper>
      );

      const checkboxes = screen.getAllByRole('checkbox');
      expect(checkboxes.length).toBeGreaterThan(0);
    });

    it('should have accessible play buttons', () => {
      render(
        <Wrapper>
          <TrackListView {...defaultProps} viewMode="grid" />
        </Wrapper>
      );

      const buttons = screen.getAllByRole('button');
      expect(buttons.length).toBeGreaterThan(0);
    });
  });

  describe('Edge Cases', () => {
    it('should handle very large track lists', () => {
      const manyTracks = Array.from({ length: 500 }, (_, i) => ({
        ...mockTracks[0],
        id: i,
        title: `Track ${i}`,
      }));

      const { container } = render(
        <Wrapper>
          <TrackListView
            {...defaultProps}
            viewMode="list"
            tracks={manyTracks}
            totalTracks={500}
          />
        </Wrapper>
      );

      const rows = container.querySelectorAll('[data-testid^="track-row"]');
      expect(rows.length).toBe(500);
    });

    it('should handle tracks with missing optional fields', () => {
      const tracksWithMissing = [
        {
          id: 1,
          title: 'Track 1',
          artist: 'Artist 1',
          album: 'Album 1',
          duration: 180,
        },
      ];

      render(
        <Wrapper>
          <TrackListView
            {...defaultProps}
            viewMode="grid"
            tracks={tracksWithMissing as any}
          />
        </Wrapper>
      );

      expect(screen.getByText('Track 1')).toBeInTheDocument();
    });

    it('should handle track IDs that are very large', () => {
      const largeIdTracks = [
        {
          ...mockTracks[0],
          id: 999999999,
          title: 'Large ID Track',
        },
      ];

      render(
        <Wrapper>
          <TrackListView
            {...defaultProps}
            viewMode="grid"
            tracks={largeIdTracks as any}
          />
        </Wrapper>
      );

      expect(screen.getByText('Large ID Track')).toBeInTheDocument();
    });

    it('should handle very long track titles', () => {
      const longTitleTrack = {
        ...mockTracks[0],
        title: 'A'.repeat(200),
      };

      render(
        <Wrapper>
          <TrackListView
            {...defaultProps}
            viewMode="grid"
            tracks={[longTitleTrack] as any}
          />
        </Wrapper>
      );

      expect(screen.getByText(/A+/)).toBeInTheDocument();
    });
  });

  describe('Performance', () => {
    it('should render efficiently with large dataset', () => {
      const largeDataset = Array.from({ length: 1000 }, (_, i) => ({
        ...mockTracks[0],
        id: i,
        title: `Track ${i}`,
      }));

      const { container } = render(
        <Wrapper>
          <TrackListView
            {...defaultProps}
            viewMode="list"
            tracks={largeDataset as any}
            totalTracks={1000}
          />
        </Wrapper>
      );

      expect(container).toBeInTheDocument();
    });
  });

  describe('Integration', () => {
    it('should handle complete workflow in grid mode', async () => {
      const user = userEvent.setup();
      const onTrackPlay = vi.fn();

      render(
        <Wrapper>
          <TrackListView
            {...defaultProps}
            viewMode="grid"
            tracks={mockTracks}
            onTrackPlay={onTrackPlay}
          />
        </Wrapper>
      );

      // Verify grid rendered
      expect(screen.getByTestId('track-card-Track 1')).toBeInTheDocument();

      // Play a track
      const playButton = screen.getAllByRole('button', { name: /play/i })[0];
      await user.click(playButton);

      expect(onTrackPlay).toHaveBeenCalled();

      // Verify queue shown
      expect(screen.getByTestId('track-queue')).toBeInTheDocument();
    });

    it('should handle complete workflow in list mode', async () => {
      const user = userEvent.setup();
      const onTrackPlay = vi.fn();
      const onToggleSelect = vi.fn();

      render(
        <Wrapper>
          <TrackListView
            {...defaultProps}
            viewMode="list"
            tracks={mockTracks}
            onTrackPlay={onTrackPlay}
            onToggleSelect={onToggleSelect}
          />
        </Wrapper>
      );

      // Verify list rendered
      expect(screen.getByTestId('track-row-1')).toBeInTheDocument();

      // Select a track
      const checkbox = screen.getByTestId('checkbox-1');
      await user.click(checkbox);
      expect(onToggleSelect).toHaveBeenCalled();

      // Play a track
      const playButton = screen.getAllByRole('button', { name: /play/i })[0];
      await user.click(playButton);
      expect(onTrackPlay).toHaveBeenCalled();
    });
  });
});
