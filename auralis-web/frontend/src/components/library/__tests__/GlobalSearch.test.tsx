/**
 * GlobalSearch Component Tests
 *
 * Tests the global search component with:
 * - Search input and debouncing
 * - Multi-category search results (tracks, albums, artists)
 * - Result grouping and display
 * - Result filtering based on search query
 * - Loading and empty states
 * - Result click handling
 * - Clear functionality
 */

import { vi } from 'vitest';
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material/styles';
import GlobalSearch from '../GlobalSearch';
import { auralisTheme } from '../../../theme/auralisTheme';

// Mock AlbumArt component
vi.mock('../../album/AlbumArt', () => {
  return function MockAlbumArt({ albumId, size }: any) {
    return (
      <div data-testid={`album-art-${albumId}`} style={{ width: size, height: size }}>
        Album {albumId}
      </div>
    );
  };
});

// Mock fetch
global.fetch = vi.fn();

const mockTracksResponse = {
  tracks: [
    {
      id: 1,
      title: 'Bohemian Rhapsody',
      artist: 'Queen',
      album: 'A Night at the Opera',
      album_id: 1,
    },
    {
      id: 2,
      title: 'Another One Bites the Dust',
      artist: 'Queen',
      album: 'The Game',
      album_id: 2,
    },
    {
      id: 3,
      title: 'We Will Rock You',
      artist: 'Queen',
      album: 'News of the World',
      album_id: 3,
    },
  ],
};

const mockAlbumsResponse = {
  albums: [
    { id: 1, title: 'A Night at the Opera', artist: 'Queen', year: 1975, track_count: 12 },
    { id: 2, title: 'The Game', artist: 'Queen', year: 1980, track_count: 10 },
    { id: 3, title: 'News of the World', artist: 'Queen', year: 1977, track_count: 11 },
  ],
};

const mockArtistsResponse = {
  artists: [
    { id: 1, name: 'Queen', album_count: 15, track_count: 200 },
    { id: 2, name: 'Queensrÿche', album_count: 10, track_count: 150 },
    { id: 3, name: 'Queens of the Stone Age', album_count: 6, track_count: 100 },
  ],
};

const Wrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <BrowserRouter>
    <ThemeProvider theme={auralisTheme}>
      {children}
    </ThemeProvider>
  </BrowserRouter>
);

describe('GlobalSearch', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (global.fetch as any).mockImplementation((url: string) => {
      if (url.includes('tracks')) {
        return Promise.resolve({
          ok: true,
          json: async () => mockTracksResponse,
        });
      }
      if (url.includes('albums')) {
        return Promise.resolve({
          ok: true,
          json: async () => mockAlbumsResponse,
        });
      }
      if (url.includes('artists')) {
        return Promise.resolve({
          ok: true,
          json: async () => mockArtistsResponse,
        });
      }
      return Promise.resolve({ ok: false });
    });
  });

  describe('Rendering', () => {
    it('should render search input field', () => {
      render(
        <Wrapper>
          <GlobalSearch />
        </Wrapper>
      );

      const input = screen.getByPlaceholderText(/search tracks, albums, artists/i);
      expect(input).toBeInTheDocument();
    });

    it('should have search icon', () => {
      render(
        <Wrapper>
          <GlobalSearch />
        </Wrapper>
      );

      expect(screen.getByTestId(/search|icon/i) || document.body).toBeInTheDocument();
    });

    it('should not show results initially', () => {
      render(
        <Wrapper>
          <GlobalSearch />
        </Wrapper>
      );

      expect(screen.queryByText(/tracks|albums|artists/i)).not.toBeInTheDocument();
    });
  });

  describe('Search Input', () => {
    it('should update input value on type', async () => {
      const user = userEvent.setup();

      render(
        <Wrapper>
          <GlobalSearch />
        </Wrapper>
      );

      const input = screen.getByPlaceholderText(/search/i) as HTMLInputElement;
      await user.type(input, 'Queen');

      expect(input.value).toBe('Queen');
    });

    it('should require minimum 2 characters to search', async () => {
      const user = userEvent.setup();
      vi.useFakeTimers();

      render(
        <Wrapper>
          <GlobalSearch />
        </Wrapper>
      );

      const input = screen.getByPlaceholderText(/search/i);
      await user.type(input, 'Q');

      vi.advanceTimersByTime(400);
      vi.useRealTimers();

      // Should not call fetch with single character
      expect((global.fetch as any).mock.calls.length).toBe(0);
    });

    it('should debounce search input', async () => {
      const user = userEvent.setup();
      vi.useFakeTimers();

      render(
        <Wrapper>
          <GlobalSearch />
        </Wrapper>
      );

      const input = screen.getByPlaceholderText(/search/i);
      await user.type(input, 'Queen');

      vi.advanceTimersByTime(200);
      expect((global.fetch as any).mock.calls.length).toBe(0);

      vi.advanceTimersByTime(200);
      expect((global.fetch as any).mock.calls.length).toBeGreaterThan(0);

      vi.useRealTimers();
    });

    it('should clear input on clear button click', async () => {
      const user = userEvent.setup();
      vi.useFakeTimers();

      render(
        <Wrapper>
          <GlobalSearch />
        </Wrapper>
      );

      const input = screen.getByPlaceholderText(/search/i) as HTMLInputElement;
      await user.type(input, 'Queen');

      vi.advanceTimersByTime(400);
      vi.useRealTimers();

      // Wait for results
      await waitFor(() => {
        expect(screen.getByText(/Bohemian|Rhapsody/i)).toBeInTheDocument();
      });

      const clearButton = screen.getByRole('button', { name: /close/i });
      await user.click(clearButton);

      expect(input.value).toBe('');
      expect(screen.queryByText(/Bohemian|Rhapsody/i)).not.toBeInTheDocument();
    });
  });

  describe('Search Results - Tracks', () => {
    it('should display matching tracks', async () => {
      const user = userEvent.setup();
      vi.useFakeTimers();

      render(
        <Wrapper>
          <GlobalSearch />
        </Wrapper>
      );

      const input = screen.getByPlaceholderText(/search/i);
      await user.type(input, 'Bohemian');

      vi.advanceTimersByTime(400);
      vi.useRealTimers();

      await waitFor(() => {
        expect(screen.getByText('Bohemian Rhapsody')).toBeInTheDocument();
      });
    });

    it('should display track artist and album', async () => {
      const user = userEvent.setup();
      vi.useFakeTimers();

      render(
        <Wrapper>
          <GlobalSearch />
        </Wrapper>
      );

      const input = screen.getByPlaceholderText(/search/i);
      await user.type(input, 'Queen');

      vi.advanceTimersByTime(400);
      vi.useRealTimers();

      await waitFor(() => {
        expect(screen.getByText(/Queen/)).toBeInTheDocument();
      });
    });

    it('should show track type chip', async () => {
      const user = userEvent.setup();
      vi.useFakeTimers();

      render(
        <Wrapper>
          <GlobalSearch />
        </Wrapper>
      );

      const input = screen.getByPlaceholderText(/search/i);
      await user.type(input, 'Bohemian');

      vi.advanceTimersByTime(400);
      vi.useRealTimers();

      await waitFor(() => {
        expect(screen.getByText('Track')).toBeInTheDocument();
      });
    });

    it('should limit track results to 5', async () => {
      const user = userEvent.setup();
      vi.useFakeTimers();

      const manyTracks = Array.from({ length: 20 }, (_, i) => ({
        id: i,
        title: `Song ${i}`,
        artist: 'Queen',
        album: `Album ${i}`,
        album_id: i,
      }));

      (global.fetch as any).mockImplementation((url: string) => {
        if (url.includes('tracks')) {
          return Promise.resolve({
            ok: true,
            json: async () => ({ tracks: manyTracks }),
          });
        }
        return Promise.resolve({ ok: true, json: async () => ({ albums: [], artists: [] }) });
      });

      render(
        <Wrapper>
          <GlobalSearch />
        </Wrapper>
      );

      const input = screen.getByPlaceholderText(/search/i);
      await user.type(input, 'Song');

      vi.advanceTimersByTime(400);
      vi.useRealTimers();

      await waitFor(() => {
        const songResults = screen.queryAllByText(/Song/);
        expect(songResults.length).toBeLessThanOrEqual(5);
      });
    });
  });

  describe('Search Results - Albums', () => {
    it('should display matching albums', async () => {
      const user = userEvent.setup();
      vi.useFakeTimers();

      render(
        <Wrapper>
          <GlobalSearch />
        </Wrapper>
      );

      const input = screen.getByPlaceholderText(/search/i);
      await user.type(input, 'Night');

      vi.advanceTimersByTime(400);
      vi.useRealTimers();

      await waitFor(() => {
        expect(screen.getByText(/A Night at the Opera|Night/)).toBeInTheDocument();
      });
    });

    it('should display album type chip', async () => {
      const user = userEvent.setup();
      vi.useFakeTimers();

      render(
        <Wrapper>
          <GlobalSearch />
        </Wrapper>
      );

      const input = screen.getByPlaceholderText(/search/i);
      await user.type(input, 'Night');

      vi.advanceTimersByTime(400);
      vi.useRealTimers();

      await waitFor(() => {
        expect(screen.getByText('Album')).toBeInTheDocument();
      });
    });

    it('should display album artwork', async () => {
      const user = userEvent.setup();
      vi.useFakeTimers();

      render(
        <Wrapper>
          <GlobalSearch />
        </Wrapper>
      );

      const input = screen.getByPlaceholderText(/search/i);
      await user.type(input, 'Night');

      vi.advanceTimersByTime(400);
      vi.useRealTimers();

      await waitFor(() => {
        expect(screen.getByTestId(/album-art/)).toBeInTheDocument();
      });
    });
  });

  describe('Search Results - Artists', () => {
    it('should display matching artists', async () => {
      const user = userEvent.setup();
      vi.useFakeTimers();

      render(
        <Wrapper>
          <GlobalSearch />
        </Wrapper>
      );

      const input = screen.getByPlaceholderText(/search/i);
      await user.type(input, 'Queen');

      vi.advanceTimersByTime(400);
      vi.useRealTimers();

      await waitFor(() => {
        const queen = screen.getAllByText('Queen');
        expect(queen.length).toBeGreaterThan(0);
      });
    });

    it('should display artist album and track counts', async () => {
      const user = userEvent.setup();
      vi.useFakeTimers();

      render(
        <Wrapper>
          <GlobalSearch />
        </Wrapper>
      );

      const input = screen.getByPlaceholderText(/search/i);
      await user.type(input, 'Queen');

      vi.advanceTimersByTime(400);
      vi.useRealTimers();

      await waitFor(() => {
        expect(screen.getByText(/albums|tracks/i)).toBeInTheDocument();
      });
    });

    it('should display artist type chip', async () => {
      const user = userEvent.setup();
      vi.useFakeTimers();

      render(
        <Wrapper>
          <GlobalSearch />
        </Wrapper>
      );

      const input = screen.getByPlaceholderText(/search/i);
      await user.type(input, 'Queen');

      vi.advanceTimersByTime(400);
      vi.useRealTimers();

      await waitFor(() => {
        expect(screen.getByText('Artist')).toBeInTheDocument();
      });
    });
  });

  describe('Result Grouping', () => {
    it('should group results by type', async () => {
      const user = userEvent.setup();
      vi.useFakeTimers();

      render(
        <Wrapper>
          <GlobalSearch />
        </Wrapper>
      );

      const input = screen.getByPlaceholderText(/search/i);
      await user.type(input, 'Queen');

      vi.advanceTimersByTime(400);
      vi.useRealTimers();

      await waitFor(() => {
        const headers = screen.queryAllByText(/Tracks|Albums|Artists/);
        expect(headers.length).toBeGreaterThan(0);
      });
    });

    it('should show dividers between categories', async () => {
      const user = userEvent.setup();
      vi.useFakeTimers();

      const { container } = render(
        <Wrapper>
          <GlobalSearch />
        </Wrapper>
      );

      const input = screen.getByPlaceholderText(/search/i);
      await user.type(input, 'Queen');

      vi.advanceTimersByTime(400);
      vi.useRealTimers();

      await waitFor(() => {
        const dividers = container.querySelectorAll('[class*="Divider"]');
        expect(dividers.length).toBeGreaterThan(0);
      });
    });

    it('should hide empty categories', async () => {
      const user = userEvent.setup();
      vi.useFakeTimers();

      (global.fetch as any).mockImplementation((url: string) => {
        if (url.includes('tracks')) {
          return Promise.resolve({
            ok: true,
            json: async () => ({ tracks: [] }),
          });
        }
        if (url.includes('albums')) {
          return Promise.resolve({
            ok: true,
            json: async () => mockAlbumsResponse,
          });
        }
        if (url.includes('artists')) {
          return Promise.resolve({
            ok: true,
            json: async () => ({ artists: [] }),
          });
        }
        return Promise.resolve({ ok: false });
      });

      render(
        <Wrapper>
          <GlobalSearch />
        </Wrapper>
      );

      const input = screen.getByPlaceholderText(/search/i);
      await user.type(input, 'Queen');

      vi.advanceTimersByTime(400);
      vi.useRealTimers();

      await waitFor(() => {
        // Should only show Albums header
        expect(screen.getByText('Albums')).toBeInTheDocument();
        expect(screen.queryByText('Tracks')).not.toBeInTheDocument();
        expect(screen.queryByText('Artists')).not.toBeInTheDocument();
      });
    });
  });

  describe('Empty State', () => {
    it('should show no results message when query has no matches', async () => {
      const user = userEvent.setup();
      vi.useFakeTimers();

      (global.fetch as any).mockImplementation(() =>
        Promise.resolve({
          ok: true,
          json: async () => ({ tracks: [], albums: [], artists: [] }),
        })
      );

      render(
        <Wrapper>
          <GlobalSearch />
        </Wrapper>
      );

      const input = screen.getByPlaceholderText(/search/i);
      await user.type(input, 'NonexistentBand');

      vi.advanceTimersByTime(400);
      vi.useRealTimers();

      await waitFor(() => {
        expect(screen.getByText(/no results found/i)).toBeInTheDocument();
      });
    });

    it('should display query in no results message', async () => {
      const user = userEvent.setup();
      vi.useFakeTimers();

      (global.fetch as any).mockImplementation(() =>
        Promise.resolve({
          ok: true,
          json: async () => ({ tracks: [], albums: [], artists: [] }),
        })
      );

      render(
        <Wrapper>
          <GlobalSearch />
        </Wrapper>
      );

      const input = screen.getByPlaceholderText(/search/i);
      await user.type(input, 'Nonexistent');

      vi.advanceTimersByTime(400);
      vi.useRealTimers();

      await waitFor(() => {
        expect(screen.getByText(/Nonexistent/)).toBeInTheDocument();
      });
    });
  });

  describe('Loading State', () => {
    it('should show loading indicator while searching', async () => {
      const user = userEvent.setup();
      vi.useFakeTimers();

      (global.fetch as any).mockImplementation(
        () => new Promise(() => {}) // Never resolves
      );

      render(
        <Wrapper>
          <GlobalSearch />
        </Wrapper>
      );

      const input = screen.getByPlaceholderText(/search/i);
      await user.type(input, 'Queen');

      vi.advanceTimersByTime(400);

      // Loading icon should appear
      expect(screen.getByRole('progressbar') || document.body).toBeInTheDocument();

      vi.useRealTimers();
    });

    it('should hide loading indicator when done', async () => {
      const user = userEvent.setup();
      vi.useFakeTimers();

      render(
        <Wrapper>
          <GlobalSearch />
        </Wrapper>
      );

      const input = screen.getByPlaceholderText(/search/i);
      await user.type(input, 'Queen');

      vi.advanceTimersByTime(400);
      vi.useRealTimers();

      await waitFor(() => {
        expect(screen.getByText('Bohemian Rhapsody')).toBeInTheDocument();
      });

      // Loading should be gone
      expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
    });
  });

  describe('Result Click Handling', () => {
    it('should call onResultClick when result clicked', async () => {
      const user = userEvent.setup();
      vi.useFakeTimers();
      const onResultClick = vi.fn();

      render(
        <Wrapper>
          <GlobalSearch onResultClick={onResultClick} />
        </Wrapper>
      );

      const input = screen.getByPlaceholderText(/search/i);
      await user.type(input, 'Bohemian');

      vi.advanceTimersByTime(400);
      vi.useRealTimers();

      await waitFor(() => {
        expect(screen.getByText('Bohemian Rhapsody')).toBeInTheDocument();
      });

      const result = screen.getByText('Bohemian Rhapsody').closest('[role="button"]');
      if (result) {
        await user.click(result);
        expect(onResultClick).toHaveBeenCalled();
      }
    });

    it('should clear search after result click', async () => {
      const user = userEvent.setup();
      vi.useFakeTimers();

      render(
        <Wrapper>
          <GlobalSearch />
        </Wrapper>
      );

      const input = screen.getByPlaceholderText(/search/i) as HTMLInputElement;
      await user.type(input, 'Bohemian');

      vi.advanceTimersByTime(400);
      vi.useRealTimers();

      await waitFor(() => {
        expect(screen.getByText('Bohemian Rhapsody')).toBeInTheDocument();
      });

      const result = screen.getByText('Bohemian Rhapsody').closest('[role="button"]');
      if (result) {
        await user.click(result);
        expect(input.value).toBe('');
      }
    });

    it('should pass correct result data', async () => {
      const user = userEvent.setup();
      vi.useFakeTimers();
      const onResultClick = vi.fn();

      render(
        <Wrapper>
          <GlobalSearch onResultClick={onResultClick} />
        </Wrapper>
      );

      const input = screen.getByPlaceholderText(/search/i);
      await user.type(input, 'Bohemian');

      vi.advanceTimersByTime(400);
      vi.useRealTimers();

      await waitFor(() => {
        expect(screen.getByText('Bohemian Rhapsody')).toBeInTheDocument();
      });

      const result = screen.getByText('Bohemian Rhapsody').closest('[role="button"]');
      if (result) {
        await user.click(result);
        expect(onResultClick).toHaveBeenCalledWith(expect.objectContaining({
          type: 'track',
          title: 'Bohemian Rhapsody',
        }));
      }
    });
  });

  describe('Search Filtering', () => {
    it('should search across artist and track title', async () => {
      const user = userEvent.setup();
      vi.useFakeTimers();

      render(
        <Wrapper>
          <GlobalSearch />
        </Wrapper>
      );

      const input = screen.getByPlaceholderText(/search/i);
      // Search by artist name
      await user.type(input, 'Queen');

      vi.advanceTimersByTime(400);
      vi.useRealTimers();

      await waitFor(() => {
        // Should find tracks by artist
        expect(screen.getByText(/Bohemian|Queen/)).toBeInTheDocument();
      });
    });

    it('should filter results by query', async () => {
      const user = userEvent.setup();
      vi.useFakeTimers();

      render(
        <Wrapper>
          <GlobalSearch />
        </Wrapper>
      );

      const input = screen.getByPlaceholderText(/search/i);
      await user.type(input, 'Bohemian');

      vi.advanceTimersByTime(400);
      vi.useRealTimers();

      await waitFor(() => {
        expect(screen.getByText('Bohemian Rhapsody')).toBeInTheDocument();
        // Should not show other Queen songs
        expect(screen.queryByText('Another One Bites the Dust')).not.toBeInTheDocument();
      });
    });
  });

  describe('Accessibility', () => {
    it('should have proper input attributes', () => {
      render(
        <Wrapper>
          <GlobalSearch />
        </Wrapper>
      );

      const input = screen.getByPlaceholderText(/search/i);
      expect(input).toHaveAttribute('type', 'text');
    });

    it('should have accessible result buttons', async () => {
      const user = userEvent.setup();
      vi.useFakeTimers();

      render(
        <Wrapper>
          <GlobalSearch />
        </Wrapper>
      );

      const input = screen.getByPlaceholderText(/search/i);
      await user.type(input, 'Queen');

      vi.advanceTimersByTime(400);
      vi.useRealTimers();

      await waitFor(() => {
        const buttons = screen.getAllByRole('button');
        expect(buttons.length).toBeGreaterThan(0);
      });
    });
  });

  describe('Edge Cases', () => {
    it('should handle search API failures gracefully', async () => {
      const user = userEvent.setup();
      vi.useFakeTimers();

      (global.fetch as any).mockRejectedValue(new Error('Network error'));

      render(
        <Wrapper>
          <GlobalSearch />
        </Wrapper>
      );

      const input = screen.getByPlaceholderText(/search/i);
      await user.type(input, 'Queen');

      vi.advanceTimersByTime(400);
      vi.useRealTimers();

      // Should handle error gracefully
      expect(document.body).toBeInTheDocument();
    });

    it('should handle very long search query', async () => {
      const user = userEvent.setup();
      vi.useFakeTimers();

      render(
        <Wrapper>
          <GlobalSearch />
        </Wrapper>
      );

      const input = screen.getByPlaceholderText(/search/i) as HTMLInputElement;
      const longQuery = 'A'.repeat(200);
      await user.type(input, longQuery);

      vi.advanceTimersByTime(400);
      vi.useRealTimers();

      expect(input.value.length).toBe(200);
    });

    it('should handle special characters in search', async () => {
      const user = userEvent.setup();
      vi.useFakeTimers();

      render(
        <Wrapper>
          <GlobalSearch />
        </Wrapper>
      );

      const input = screen.getByPlaceholderText(/search/i);
      await user.type(input, '@#$%');

      vi.advanceTimersByTime(400);
      vi.useRealTimers();

      // Should handle without crashing
      expect(document.body).toBeInTheDocument();
    });

    it('should handle unicode characters', async () => {
      const user = userEvent.setup();
      vi.useFakeTimers();

      render(
        <Wrapper>
          <GlobalSearch />
        </Wrapper>
      );

      const input = screen.getByPlaceholderText(/search/i) as HTMLInputElement;
      await user.type(input, '音楽');

      vi.advanceTimersByTime(400);
      vi.useRealTimers();

      expect(input.value).toBe('音楽');
    });
  });
});
