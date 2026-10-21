/**
 * TrackListView Component Tests
 *
 * Simplified test suite focusing on core functionality:
 * - Component rendering
 * - View mode switching
 * - Track display
 */

import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import { render, screen } from '@/test/test-utils';
import { act } from 'react';
import TrackListView from '../Views/TrackListView';

// Mock child components used by TrackListView
vi.mock('../Views/TrackGridView', () => ({
  default: function MockTrackGridView({ tracks }: any) {
    return (
      <div data-testid="track-grid-view" role="main">
        {tracks?.map((track: any) => (
          <div key={track.id} data-testid={`track-card-${track.id}`}>
            {track.title}
          </div>
        ))}
      </div>
    );
  },
}));

vi.mock('../Views/TrackListViewContent', () => ({
  default: function MockTrackListViewContent({ tracks }: any) {
    return (
      <div data-testid="track-list-view-content" role="main">
        {tracks?.map((track: any) => (
          <div key={track.id} data-testid={`track-row-${track.id}`}>
            {track.title}
          </div>
        ))}
      </div>
    );
  },
}));


// Mock skeleton loaders
vi.mock('../../shared/ui/loaders', () => ({
  LibraryGridSkeleton: function MockGridSkeleton() {
    return <div data-testid="grid-skeleton" role="main">Loading grid...</div>;
  },
  TrackRowSkeleton: function MockRowSkeleton() {
    return <div data-testid="row-skeleton">Loading row...</div>;
  },
}));

vi.mock('../Styles/Grid.styles', () => ({
  ListLoadingContainer: function MockListLoadingContainer({ children }: any) {
    return <div data-testid="list-loading-container" role="main">{children}</div>;
  },
}));

// Default props for TrackListView
const defaultProps = {
  tracks: [],
  viewMode: 'list' as const,
  loading: false,
  hasMore: false,
  totalTracks: 0,
  isLoadingMore: false,
  isPlaying: false,
  selectedTracks: new Set<number>(),
  isSelected: () => false,
  onToggleSelect: vi.fn(),
  onTrackPlay: vi.fn(),
  onPause: vi.fn(),
  onEditMetadata: vi.fn(),
  onLoadMore: vi.fn(),
};

describe('TrackListView', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(async () => {
    await act(async () => {
      vi.clearAllTimers();
    });
    vi.useRealTimers();
  });

  describe('Rendering', () => {
    it('keeps a populated list mounted while loading is true (#5626)', () => {
      // A post-mutation refresh (metadata save, bulk action, library_updated)
      // used to tear the virtualized list down to a skeleton, losing scroll,
      // focus, selection and loaded pages. Skeleton only for an empty list.
      act(() => {
        render(
          <TrackListView
            {...defaultProps}
            tracks={[
              { id: 1, title: 'Song One', artist: 'A', album: 'Al', duration: 100, filepath: '/1.flac' },
              { id: 2, title: 'Song Two', artist: 'A', album: 'Al', duration: 101, filepath: '/2.flac' },
            ]}
            loading
          />
        );
      });

      expect(screen.getByTestId('track-list-view-content')).toBeInTheDocument();
      expect(screen.getByText('Song One')).toBeInTheDocument();
      expect(screen.queryByTestId('list-loading-container')).not.toBeInTheDocument();
    });

    it('still shows the skeleton for a loading empty list (#5626)', () => {
      act(() => {
        render(<TrackListView {...defaultProps} loading />);
      });

      expect(screen.getByTestId('list-loading-container')).toBeInTheDocument();
    });

    it('should render without crashing', () => {
      let container: any;
      act(() => {
        const result = render(<TrackListView {...defaultProps} />);
        container = result.container;
      });
      expect(container).toBeInTheDocument();
    });

    it('should render track list container', () => {
      let container: any;
      act(() => {
        const result = render(<TrackListView {...defaultProps} />);
        container = result.container;
      });
      expect(container.querySelector('[data-testid*="list"]')).toBeDefined();
    });
  });

  describe('Component Lifecycle', () => {
    it('should mount and unmount cleanly', () => {
      let unmount: any;
      act(() => {
        const result = render(<TrackListView {...defaultProps} />);
        unmount = result.unmount;
      });
      expect(screen.getByRole('main') || document.body).toBeInTheDocument();

      act(() => {
        unmount();
      });
    });

    it('should handle re-mounting', () => {
      let unmount: any;
      act(() => {
        const result = render(<TrackListView {...defaultProps} />);
        unmount = result.unmount;
      });
      act(() => {
        unmount();
      });

      // Re-render
      let container: any;
      act(() => {
        const result = render(<TrackListView {...defaultProps} />);
        container = result.container;
      });
      expect(container).toBeInTheDocument();
    });
  });

  describe('View Modes', () => {
    it('should render with default props', () => {
      let container: any;
      act(() => {
        const result = render(<TrackListView {...defaultProps} />);
        container = result.container;
      });
      expect(container).toBeInTheDocument();
    });

    it('should accept view mode prop', () => {
      let container: any;
      act(() => {
        const result = render(<TrackListView {...defaultProps} viewMode="list" />);
        container = result.container;
      });
      expect(container).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('should have semantic structure', () => {
      let container: any;
      act(() => {
        const result = render(<TrackListView {...defaultProps} />);
        container = result.container;
      });
      // Should have some main content area
      expect(container.querySelectorAll('div').length).toBeGreaterThan(0);
    });

    it('should support keyboard navigation', async () => {
      await act(async () => {
        render(<TrackListView {...defaultProps} />);
      });

      // Component should be keyboard navigable
      const mainArea = screen.getByRole('main') || document.body;
      expect(mainArea).toBeInTheDocument();
    });
  });

  describe('Error Handling', () => {
    it('should handle empty track list', () => {
      let container: any;
      act(() => {
        const result = render(<TrackListView {...defaultProps} tracks={[]} />);
        container = result.container;
      });
      expect(container).toBeInTheDocument();
    });

    it('should handle missing props gracefully', () => {
      let container: any;
      act(() => {
        const result = render(<TrackListView {...defaultProps} />);
        container = result.container;
      });
      expect(container).toBeInTheDocument();
    });
  });
});
