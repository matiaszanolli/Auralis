/**
 * CozyLibraryView Component Tests
 *
 * Tests for the refactored CozyLibraryView orchestrator component.
 * The component now uses extracted sub-components and hooks:
 * - ViewContainer for layout
 * - TrackListView for track rendering
 * - EmptyState components for empty states
 * - useLibraryWithStats for data fetching
 */

import { vi } from 'vitest';
import { render, screen } from '@/test/test-utils';
import CozyLibraryView from '../library/CozyLibraryView';
import { useLibraryWithStats } from '@/hooks/library/useLibraryWithStats';
import { usePlayerAPI } from '@/hooks/player/usePlayerAPI';

vi.mock('@/hooks/library/useLibraryWithStats', () => ({
  useLibraryWithStats: vi.fn(),
}));
vi.mock('@/hooks/player/usePlayerAPI', () => ({
  usePlayerAPI: vi.fn(),
}));
vi.mock('@/contexts/WebSocketContext', () => ({
  useWebSocketContext: () => ({
    subscribe: vi.fn(() => vi.fn()),
    unsubscribe: vi.fn(),
    sendMessage: vi.fn(),
    isConnected: true,
  }),
  WebSocketProvider: ({ children }: any) => children,
}));
vi.mock('@/hooks/fingerprint/useAlbumFingerprint', () => ({
  useAlbumFingerprint: () => ({
    data: null,
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }),
}));
vi.mock('../library/AlbumCharacterPane', () => ({
  AlbumCharacterPane: function MockAlbumCharacterPane() {
    return <div data-testid="album-character-pane">Album Character Pane</div>;
  },
}));
vi.mock('../library/Views/TrackListView', () => ({
  TrackListView: function MockTrackListView({ tracks }: any) {
    return (
      <div data-testid="track-list-view">
        {tracks.map((track: any) => (
          <div key={track.id} data-testid={`track-${track.id}`}>
            {track.title}
          </div>
        ))}
      </div>
    );
  },
}));
vi.mock('../shared/ui/feedback', () => ({
  EmptyState: function MockEmptyState({ title }: any) {
    return <div data-testid="empty-state">{title}</div>;
  },
  EmptyLibrary: function MockEmptyLibrary() {
    return <div data-testid="empty-library">No music yet</div>;
  },
  NoSearchResults: function MockNoSearchResults({ query }: any) {
    return <div data-testid="no-results">No results for {query}</div>;
  },
}));

const mockLibraryWithStats = {
  // Data
  tracks: [
    { id: 1, title: 'Track 1', artist: 'Artist 1', album: 'Album 1', duration: 180 },
    { id: 2, title: 'Track 2', artist: 'Artist 2', album: 'Album 2', duration: 220 },
  ],
  stats: {
    total_tracks: 100,
    total_artists: 25,
    total_albums: 15,
    total_genres: 8,
    total_playlists: 3,
    total_duration: 36000,
    total_duration_formatted: '10 hours',
    total_filesize: 5000000000,
    total_filesize_gb: 5.0
  },

  // State
  loading: false,
  error: null,
  hasMore: true,
  totalTracks: 100,
  offset: 0,
  isLoadingMore: false,
  scanning: false,
  statsLoading: false,

  // Methods
  fetchTracks: vi.fn(),
  loadMore: vi.fn(),
  handleScanFolder: vi.fn(),
  refetchStats: vi.fn(),
  isElectron: vi.fn(() => false),
};

const mockPlayerAPI = {
  play: vi.fn(),
  playTrack: vi.fn(),
  addToQueue: vi.fn(),
  pause: vi.fn(),
  currentTrack: null,
  isPlaying: false,
} as any;

describe('CozyLibraryView', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Set default mock return values
    vi.mocked(useLibraryWithStats).mockReturnValue(mockLibraryWithStats as any);
    vi.mocked(usePlayerAPI).mockReturnValue(mockPlayerAPI);
  });

  describe('Rendering', () => {
    it('should render without crashing', () => {
      const { container } = render(<CozyLibraryView />);
      expect(container.firstChild).toBeInTheDocument();
    });

    it('should render ViewContainer with track list', () => {
      render(<CozyLibraryView />);

      // Should render the mocked track list with tracks
      expect(screen.getByTestId('track-list-view')).toBeInTheDocument();
      expect(screen.getByText('Track 1')).toBeInTheDocument();
      expect(screen.getByText('Track 2')).toBeInTheDocument();
    });

    it('should render AlbumCharacterPane', () => {
      render(<CozyLibraryView />);
      expect(screen.getByTestId('album-character-pane')).toBeInTheDocument();
    });
  });

  describe('Empty States', () => {
    it('should show empty library when no tracks', () => {
      // Override the default mock for this test
      vi.mocked(useLibraryWithStats).mockReturnValue({
        ...mockLibraryWithStats,
        tracks: [],
      } as any);

      render(<CozyLibraryView />);
      expect(screen.getByTestId('empty-library')).toBeInTheDocument();
    });

    it('should show empty state for favorites view when no tracks', () => {
      // Override the default mock for this test
      vi.mocked(useLibraryWithStats).mockReturnValue({
        ...mockLibraryWithStats,
        tracks: [],
      } as any);

      render(<CozyLibraryView view="favourites" />);
      expect(screen.getByTestId('empty-state')).toBeInTheDocument();
    });
  });

  describe('Loading State', () => {
    it('should handle loading state', () => {
      // Override the default mock for this test
      vi.mocked(useLibraryWithStats).mockReturnValue({
        ...mockLibraryWithStats,
        loading: true,
      } as any);

      const { container } = render(<CozyLibraryView />);
      expect(container.firstChild).toBeInTheDocument();
    });
  });

  describe('Data Integration', () => {
    it('should call useLibraryWithStats with correct view', () => {
      render(<CozyLibraryView view="favourites" />);

      expect(useLibraryWithStats).toHaveBeenCalledWith({
        view: 'favourites',
        includeStats: false,
      });
    });

    it('should pass tracks to TrackListView', () => {
      render(<CozyLibraryView />);

      // Verify tracks are rendered (via our mock)
      expect(screen.getByTestId('track-1')).toBeInTheDocument();
      expect(screen.getByTestId('track-2')).toBeInTheDocument();
    });
  });

  describe('Enhancement Integration', () => {
    it('should render with enhancement controls', () => {
      const onEnhancementToggle = vi.fn();

      render(
        <CozyLibraryView
          isEnhancementEnabled={true}
          onEnhancementToggle={onEnhancementToggle}
        />
      );

      // AlbumCharacterPane should be rendered with enhancement props
      expect(screen.getByTestId('album-character-pane')).toBeInTheDocument();
    });
  });
});
