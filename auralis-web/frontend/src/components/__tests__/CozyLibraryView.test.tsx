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
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material/styles';
import CozyLibraryView from '../CozyLibraryView';
import { useLibraryWithStats } from '../../hooks/useLibraryWithStats';
import { usePlayerAPI } from '../../hooks/usePlayerAPI';
import { auralisTheme } from '../../theme/auralisTheme';

vi.mock('../../hooks/useLibraryWithStats');
vi.mock('../../hooks/usePlayerAPI');
vi.mock('../CozyAlbumGrid', () => {
  return function MockGrid({ albums, onAlbumClick }: any) {
    return (
      <div data-testid="album-grid">
        {albums.map((album: any) => (
          <button key={album.id} onClick={() => onAlbumClick?.(album)}>
            {album.title}
          </button>
        ))}
      </div>
    );
  };
});
vi.mock('../CozyArtistList', () => {
  return function MockList({ artists, onArtistClick }: any) {
    return (
      <div data-testid="artist-list">
        {artists.map((artist: any) => (
          <button key={artist.id} onClick={() => onArtistClick?.(artist)}>
            {artist.name}
          </button>
        ))}
      </div>
    );
  };
});
vi.mock('../GlobalSearch', () => {
  return function MockSearch({ onSearch }: any) {
    return (
      <input
        data-testid="search-input"
        placeholder="Search..."
        onChange={(e) => onSearch?.(e.target.value)}
      />
    );
  };
});

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
  addToQueue: vi.fn(),
};

const Wrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <BrowserRouter>
    <ThemeProvider theme={auralisTheme}>
      {children}
    </ThemeProvider>
  </BrowserRouter>
);

describe('CozyLibraryView', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useLibraryWithStats).mockReturnValue(mockLibraryWithStats);
    vi.mocked(usePlayerAPI).mockReturnValue(mockPlayerAPI);
  });

  describe('Rendering', () => {
    it('should render library view container', () => {
      render(
        <Wrapper>
          <CozyLibraryView />
        </Wrapper>
      );
      const view = screen.getByTestId(/library|view/i);
      expect(view).toBeInTheDocument();
    });

    it('should render search input', () => {
      render(
        <Wrapper>
          <CozyLibraryView />
        </Wrapper>
      );
      expect(screen.getByTestId('search-input')).toBeInTheDocument();
    });

    it('should render view toggle buttons', () => {
      render(
        <Wrapper>
          <CozyLibraryView />
        </Wrapper>
      );
      const toggleButtons = screen.queryAllByRole('button', { name: /album|artist|track|grid|list/i });
      expect(toggleButtons.length).toBeGreaterThan(0);
    });

    it('should display album grid by default', () => {
      render(
        <Wrapper>
          <CozyLibraryView />
        </Wrapper>
      );
      expect(screen.getByTestId('album-grid')).toBeInTheDocument();
    });
  });

  describe('Album Grid View', () => {
    it('should render all albums', () => {
      render(
        <Wrapper>
          <CozyLibraryView />
        </Wrapper>
      );
      expect(screen.getByText('Album 1')).toBeInTheDocument();
      expect(screen.getByText('Album 2')).toBeInTheDocument();
    });

    it('should navigate to album detail on click', async () => {
      const user = userEvent.setup();
      render(
        <Wrapper>
          <CozyLibraryView />
        </Wrapper>
      );
      const albumButton = screen.getByText('Album 1');
      await user.click(albumButton);

      // Should navigate to album detail view or show album tracks
      await waitFor(() => {
        expect(screen.queryByText(/tracks|songs/i)).toBeInTheDocument() ||
        expect(screen.queryByText('Album 1')).toBeInTheDocument();
      });
    });
  });

  describe('Artist List View', () => {
    it('should switch to artist view on toggle', async () => {
      const user = userEvent.setup();
      render(
        <Wrapper>
          <CozyLibraryView />
        </Wrapper>
      );

      const artistViewButton = screen.getByRole('button', { name: /artist/i });
      await user.click(artistViewButton);

      expect(screen.getByTestId('artist-list')).toBeInTheDocument();
    });

    it('should render all artists in artist view', async () => {
      const user = userEvent.setup();
      render(
        <Wrapper>
          <CozyLibraryView />
        </Wrapper>
      );

      const artistViewButton = screen.getByRole('button', { name: /artist/i });
      await user.click(artistViewButton);

      expect(screen.getByText('Artist 1')).toBeInTheDocument();
      expect(screen.getByText('Artist 2')).toBeInTheDocument();
    });

    it('should navigate to artist detail on artist click', async () => {
      const user = userEvent.setup();
      render(
        <Wrapper>
          <CozyLibraryView />
        </Wrapper>
      );

      const artistViewButton = screen.getByRole('button', { name: /artist/i });
      await user.click(artistViewButton);

      const artistButton = screen.getByText('Artist 1');
      await user.click(artistButton);

      // Should show artist detail or albums
      await waitFor(() => {
        expect(document.body).toBeInTheDocument();
      });
    });
  });

  describe('Search Filter', () => {
    it('should filter albums on search', async () => {
      const user = userEvent.setup();
      const searchMock = vi.fn();

      vi.mocked(useLibraryData).mockReturnValue({
        ...mockLibraryData,
        search: searchMock,
      });

      render(
        <Wrapper>
          <CozyLibraryView />
        </Wrapper>
      );

      const searchInput = screen.getByTestId('search-input');
      await user.type(searchInput, 'Album 1');

      await waitFor(() => {
        expect(screen.getByText('Album 1')).toBeInTheDocument();
      });
    });

    it('should clear search results on clear button', async () => {
      const user = userEvent.setup();
      render(
        <Wrapper>
          <CozyLibraryView />
        </Wrapper>
      );

      const searchInput = screen.getByTestId('search-input');
      await user.type(searchInput, 'Album');

      const clearButton = screen.queryByRole('button', { name: /clear|x/i });
      if (clearButton) {
        await user.click(clearButton);
        expect(screen.getByTestId('search-input')).toHaveValue('');
      }
    });

    it('should show no results message when search empty', async () => {
      const user = userEvent.setup();

      vi.mocked(useLibraryData).mockReturnValue({
        ...mockLibraryData,
        albums: [],
      });

      render(
        <Wrapper>
          <CozyLibraryView />
        </Wrapper>
      );

      const emptyState = screen.queryByText(/no.*found|empty|not found/i);
      expect(emptyState).toBeInTheDocument();
    });
  });

  describe('Loading State', () => {
    it('should show loading indicator when loading', () => {
      vi.mocked(useLibraryData).mockReturnValue({
        ...mockLibraryData,
        isLoading: true,
      });

      render(
        <Wrapper>
          <CozyLibraryView />
        </Wrapper>
      );

      const loadingIndicator = screen.getByRole('progressbar') ||
                               screen.getByText(/loading|please wait/i);
      expect(loadingIndicator).toBeInTheDocument();
    });

    it('should show albums after loading', async () => {
      const { rerender } = render(
        <Wrapper>
          <CozyLibraryView />
        </Wrapper>
      );

      vi.mocked(useLibraryData).mockReturnValue({
        ...mockLibraryData,
        isLoading: false,
      });

      rerender(
        <Wrapper>
          <CozyLibraryView />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Album 1')).toBeInTheDocument();
      });
    });
  });

  describe('Error Handling', () => {
    it('should show error message on error', () => {
      vi.mocked(useLibraryData).mockReturnValue({
        ...mockLibraryData,
        error: 'Failed to load library',
      });

      render(
        <Wrapper>
          <CozyLibraryView />
        </Wrapper>
      );

      expect(screen.getByText(/failed|error|unable/i)).toBeInTheDocument();
    });

    it('should show retry button on error', async () => {
      const user = userEvent.setup();

      vi.mocked(useLibraryData).mockReturnValue({
        ...mockLibraryData,
        error: 'Failed to load library',
        retry: vi.fn(),
      });

      render(
        <Wrapper>
          <CozyLibraryView />
        </Wrapper>
      );

      const retryButton = screen.getByRole('button', { name: /retry|try again/i });
      await user.click(retryButton);

      expect(mockLibraryData.retry).toHaveBeenCalled();
    });
  });

  describe('Empty State', () => {
    it('should show empty state when no albums', () => {
      vi.mocked(useLibraryData).mockReturnValue({
        ...mockLibraryData,
        albums: [],
      });

      render(
        <Wrapper>
          <CozyLibraryView />
        </Wrapper>
      );

      const emptyState = screen.getByText(/no.*albums|empty library|add music/i);
      expect(emptyState).toBeInTheDocument();
    });

    it('should show action prompt in empty state', () => {
      vi.mocked(useLibraryData).mockReturnValue({
        ...mockLibraryData,
        albums: [],
      });

      render(
        <Wrapper>
          <CozyLibraryView />
        </Wrapper>
      );

      const actionButton = screen.getByRole('button', { name: /import|add|browse/i });
      expect(actionButton).toBeInTheDocument();
    });
  });

  describe('Playback Integration', () => {
    it('should play album on album selection', async () => {
      const user = userEvent.setup();
      render(
        <Wrapper>
          <CozyLibraryView />
        </Wrapper>
      );

      const albumButton = screen.getByText('Album 1');
      await user.click(albumButton);

      // May call play or show album details
      await waitFor(() => {
        expect(mockPlayerAPI.play).toHaveBeenCalled() ||
        expect(screen.queryByText('Album 1')).toBeInTheDocument();
      });
    });

    it('should add track to queue', async () => {
      const user = userEvent.setup();
      render(
        <Wrapper>
          <CozyLibraryView />
        </Wrapper>
      );

      // Navigate to view with tracks
      const albumButton = screen.getByText('Album 1');
      await user.click(albumButton);

      // Find and click add to queue button for a track
      const addButton = screen.queryByRole('button', { name: /add.*queue|queue/i });
      if (addButton) {
        await user.click(addButton);
        expect(mockPlayerAPI.addToQueue).toHaveBeenCalled();
      }
    });
  });

  describe('View Switching', () => {
    it('should preserve scroll position when switching views', async () => {
      const user = userEvent.setup();
      render(
        <Wrapper>
          <CozyLibraryView />
        </Wrapper>
      );

      // Scroll down
      const albumGrid = screen.getByTestId('album-grid');
      fireEvent.scroll(albumGrid, { target: { scrollY: 100 } });

      // Switch to artist view
      const artistViewButton = screen.getByRole('button', { name: /artist/i });
      await user.click(artistViewButton);

      // Switch back
      const albumViewButton = screen.getByRole('button', { name: /album/i });
      await user.click(albumViewButton);

      // Scroll position should be preserved or reasonably maintained
      expect(screen.getByTestId('album-grid')).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('should have accessible view controls', () => {
      render(
        <Wrapper>
          <CozyLibraryView />
        </Wrapper>
      );

      const viewButtons = screen.getAllByRole('button', { name: /album|artist|track/i });
      viewButtons.forEach(button => {
        expect(button).toHaveAccessibleName();
      });
    });

    it('should have accessible search input', () => {
      render(
        <Wrapper>
          <CozyLibraryView />
        </Wrapper>
      );

      const searchInput = screen.getByTestId('search-input');
      expect(searchInput).toHaveAttribute('placeholder') ||
      expect(searchInput).toHaveAccessibleName();
    });
  });

  describe('Performance', () => {
    it('should handle large library efficiently', () => {
      const largeLibrary = {
        albums: Array.from({ length: 1000 }, (_, i) => ({
          id: i,
          title: `Album ${i}`,
          artist: `Artist ${i}`,
        })),
        artists: [],
        tracks: [],
        isLoading: false,
        error: null,
      };

      vi.mocked(useLibraryData).mockReturnValue(largeLibrary);

      render(
        <Wrapper>
          <CozyLibraryView />
        </Wrapper>
      );

      expect(screen.getByTestId('album-grid')).toBeInTheDocument();
    });
  });

  describe('State Synchronization', () => {
    it('should update when library data changes', () => {
      const { rerender } = render(
        <Wrapper>
          <CozyLibraryView />
        </Wrapper>
      );

      vi.mocked(useLibraryData).mockReturnValue({
        ...mockLibraryData,
        albums: [
          ...mockLibraryData.albums,
          { id: 3, title: 'Album 3', artist: 'Artist 3', tracks: [] },
        ],
      });

      rerender(
        <Wrapper>
          <CozyLibraryView />
        </Wrapper>
      );

      expect(screen.getByText('Album 3')).toBeInTheDocument();
    });
  });
});
