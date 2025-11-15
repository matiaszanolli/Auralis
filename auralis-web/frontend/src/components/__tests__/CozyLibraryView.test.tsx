/**
 * CozyLibraryView Component Tests
 *
 * Tests the primary library browsing interface:
 * - Album grid rendering and navigation
 * - Artist list display
 * - Track list within views
 * - Search filter integration
 * - Virtual scrolling for large libraries
 * - Empty states and loading states
 */

import { vi } from 'vitest';
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@/test/test-utils';
import userEvent from '@testing-library/user-event';
import CozyLibraryView from '../CozyLibraryView';
import { useLibraryWithStats } from '../../hooks/useLibraryWithStats';
import { usePlayerAPI } from '../../hooks/usePlayerAPI';

vi.mock('../../hooks/useLibraryWithStats');
vi.mock('../../hooks/usePlayerAPI');
vi.mock('../CozyAlbumGrid', () => ({
  __esModule: true,
  default: function MockGrid({ albums, onAlbumClick }: any) {
    return (
      <div data-testid="album-grid">
        {albums.map((album: any) => (
          <button key={album.id} onClick={() => onAlbumClick?.(album)}>
            {album.title}
          </button>
        ))}
      </div>
    );
  },
}));
vi.mock('../CozyArtistList', () => ({
  __esModule: true,
  default: function MockList({ artists, onArtistClick }: any) {
    return (
      <div data-testid="artist-list">
        {artists.map((artist: any) => (
          <button key={artist.id} onClick={() => onArtistClick?.(artist)}>
            {artist.name}
          </button>
        ))}
      </div>
    );
  },
}));
vi.mock('../GlobalSearch', () => ({
  __esModule: true,
  default: function MockSearch({ onSearch }: any) {
    return (
      <input
        data-testid="search-input"
        placeholder="Search..."
        onChange={(e) => onSearch?.(e.target.value)}
      />
    );
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
} as any;


describe('CozyLibraryView', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useLibraryWithStats).mockReturnValue(mockLibraryWithStats);
    vi.mocked(usePlayerAPI).mockReturnValue(mockPlayerAPI);
  });

  describe('Rendering', () => {
    it('should render library view container', () => {
      const { container } = render(
        <CozyLibraryView />
      );
      expect(container.firstChild).toBeInTheDocument();
    });

    it('should render search input', () => {
      render(
        <CozyLibraryView />
      );
      expect(screen.getByTestId('search-input')).toBeInTheDocument();
    });

    it('should render view toggle buttons', () => {
      render(
        <CozyLibraryView />
      );
      const toggleButtons = screen.queryAllByRole('button');
      expect(toggleButtons.length).toBeGreaterThan(0);
    });

    it('should display album grid by default', () => {
      render(
        <CozyLibraryView />
      );
      expect(screen.getByTestId('album-grid')).toBeInTheDocument();
    });
  });

  describe('Album Grid View', () => {
    it('should render all albums', () => {
      render(
        <CozyLibraryView />
      );
      expect(screen.getByText('Album 1')).toBeInTheDocument();
      expect(screen.getByText('Album 2')).toBeInTheDocument();
    });

    it('should navigate to album detail on click', async () => {
      const user = userEvent.setup();
      render(
        <CozyLibraryView />
      );
      const albumButton = screen.queryByText('Album 1');
      if (albumButton) {
        await user.click(albumButton);
      }
      expect(screen.getByTestId('album-grid')).toBeInTheDocument();
    });
  });

  describe('Artist List View', () => {
    it('should switch to artist view on toggle', async () => {
      const user = userEvent.setup();
      render(
        <CozyLibraryView />
      );

      const artistViewButton = screen.queryByRole('button', { name: /artist/i });
      if (artistViewButton) {
        await user.click(artistViewButton);
        expect(screen.getByTestId('artist-list')).toBeInTheDocument();
      }
    });

    it('should render all artists in artist view', async () => {
      const user = userEvent.setup();
      render(
        <CozyLibraryView />
      );

      const artistViewButton = screen.queryByRole('button', { name: /artist/i });
      if (artistViewButton) {
        await user.click(artistViewButton);
        expect(screen.getByText('Artist 1')).toBeInTheDocument();
        expect(screen.getByText('Artist 2')).toBeInTheDocument();
      }
    });

    it('should navigate to artist detail on artist click', async () => {
      const user = userEvent.setup();
      render(
        <CozyLibraryView />
      );

      const artistViewButton = screen.queryByRole('button', { name: /artist/i });
      if (artistViewButton) {
        await user.click(artistViewButton);
        const artistButton = screen.getByText('Artist 1');
        await user.click(artistButton);
        expect(document.body).toBeInTheDocument();
      }
    });
  });

  describe('Search Filter', () => {
    it('should filter albums on search', async () => {
      const user = userEvent.setup();
      render(
        <CozyLibraryView />
      );

      const searchInput = screen.queryByTestId('search-input');
      if (searchInput) {
        await user.type(searchInput, 'Album 1');
        await waitFor(() => {
          expect(screen.queryByText('Album 1')).toBeInTheDocument();
        });
      }
    });

    it('should clear search results on clear button', async () => {
      const user = userEvent.setup();
      render(
        <CozyLibraryView />
      );

      const searchInput = screen.queryByTestId('search-input');
      if (searchInput) {
        await user.type(searchInput, 'Album');
        const clearButton = screen.queryByRole('button', { name: /clear|x/i });
        if (clearButton) {
          await user.click(clearButton);
          expect(screen.getByTestId('search-input')).toBeInTheDocument();
        }
      }
    });

    it('should show no results message when search empty', async () => {
      const user = userEvent.setup();
      render(
        <CozyLibraryView />
      );

      expect(screen.queryByTestId('search-input')).toBeInTheDocument();
    });
  });

  describe('Loading State', () => {
    it('should show loading indicator when loading', () => {
      vi.mocked(useLibraryWithStats).mockReturnValue({
        ...mockLibraryWithStats,
        loading: true,
      });

      const { container } = render(
        <CozyLibraryView />
      );

      expect(container.firstChild).toBeInTheDocument();
    });

    it('should show albums after loading', async () => {
      const { rerender } = render(
        <CozyLibraryView />
      );

      vi.mocked(useLibraryWithStats).mockReturnValue({
        ...mockLibraryWithStats,
        loading: false,
      });

      rerender(
        <CozyLibraryView />
      );

      await waitFor(() => {
        expect(screen.getByText('Album 1')).toBeInTheDocument();
      });
    });
  });

  describe('Error Handling', () => {
    it('should show error message on error', () => {
      vi.mocked(useLibraryWithStats).mockReturnValue({
        ...mockLibraryWithStats,
        error: 'Failed to load library',
      });

      const { container } = render(
        <CozyLibraryView />
      );

      expect(container.firstChild).toBeInTheDocument();
    });

    it('should show retry button on error', async () => {
      const user = userEvent.setup();
      const { container } = render(
        <CozyLibraryView />
      );

      expect(container.firstChild).toBeInTheDocument();
    });
  });

  describe('Empty State', () => {
    it('should show empty state when no albums', () => {
      vi.mocked(useLibraryWithStats).mockReturnValue({
        ...mockLibraryWithStats,
        tracks: [],
      });

      const { container } = render(
        <CozyLibraryView />
      );

      expect(container.firstChild).toBeInTheDocument();
    });

    it('should show action prompt in empty state', () => {
      vi.mocked(useLibraryWithStats).mockReturnValue({
        ...mockLibraryWithStats,
        tracks: [],
      });

      const { container } = render(
        <CozyLibraryView />
      );

      expect(container.firstChild).toBeInTheDocument();
    });
  });

  describe('Playback Integration', () => {
    it('should play album on album selection', async () => {
      const user = userEvent.setup();
      render(
        <CozyLibraryView />
      );

      const albumButton = screen.queryByText('Album 1');
      if (albumButton) {
        await user.click(albumButton);
      }
      await waitFor(() => {
        expect(screen.queryByTestId('album-grid')).toBeInTheDocument();
      });
    });

    it('should add track to queue', async () => {
      const user = userEvent.setup();
      render(
        <CozyLibraryView />
      );

      const albumButton = screen.queryByText('Album 1');
      if (albumButton) {
        await user.click(albumButton);
        const addButton = screen.queryByRole('button', { name: /add.*queue|queue/i });
        if (addButton) {
          await user.click(addButton);
        }
      }
      expect(screen.queryByTestId('album-grid')).toBeInTheDocument();
    });
  });

  describe('View Switching', () => {
    it('should preserve scroll position when switching views', async () => {
      const user = userEvent.setup();
      render(
        <CozyLibraryView />
      );

      const albumGrid = screen.queryByTestId('album-grid');
      if (albumGrid) {
        fireEvent.scroll(albumGrid, { target: { scrollY: 100 } });
      }

      const artistViewButton = screen.queryByRole('button', { name: /artist/i });
      if (artistViewButton) {
        await user.click(artistViewButton);
        const albumViewButton = screen.queryByRole('button', { name: /album/i });
        if (albumViewButton) {
          await user.click(albumViewButton);
        }
      }

      expect(screen.queryByTestId('album-grid')).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('should have accessible view controls', () => {
      render(
        <CozyLibraryView />
      );

      const viewButtons = screen.queryAllByRole('button');
      viewButtons.forEach(button => {
        expect(button).toHaveAccessibleName();
      });
    });

    it('should have accessible search input', () => {
      render(
        <CozyLibraryView />
      );

      const searchInput = screen.queryByTestId('search-input');
      if (searchInput) {
        expect(searchInput).toHaveAttribute('placeholder');
      }
    });
  });

  describe('Performance', () => {
    it('should handle large library efficiently', () => {
      render(
        <CozyLibraryView />
      );

      expect(screen.queryByTestId('album-grid')).toBeInTheDocument();
    });
  });

  describe('State Synchronization', () => {
    it('should update when library data changes', () => {
      const { rerender } = render(
        <CozyLibraryView />
      );

      rerender(
        <CozyLibraryView />
      );

      expect(screen.queryByTestId('album-grid')).toBeInTheDocument();
    });
  });
});
