/**
 * Filter Integration Tests
 *
 * Tests for filter functionality including genre, year range, and favorites filtering.
 *
 * Test Categories:
 * 1. Filter Combinations (5 tests)
 *
 * Previously part of search-filter-accessibility.test.tsx
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import { render } from '@/test/test-utils';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from '@/test/mocks/server';
import * as React from 'react';

// Mock filterable library component
const FilterableLibrary = () => {
  const [genre, setGenre] = React.useState('');
  const [yearRange, setYearRange] = React.useState<[number, number] | null>(null);
  const [favoritesOnly, setFavoritesOnly] = React.useState(false);
  const [tracks, setTracks] = React.useState<any[]>([]);

  React.useEffect(() => {
    const fetchTracks = async () => {
      const params = new URLSearchParams();
      if (genre) params.set('genre', genre);
      if (yearRange) {
        params.set('year_min', yearRange[0].toString());
        params.set('year_max', yearRange[1].toString());
      }
      if (favoritesOnly) params.set('favorites', 'true');

      const response = await fetch(
        `http://localhost:8765/api/library/tracks?${params.toString()}`
      );
      const data = await response.json();
      setTracks(data.tracks);
    };

    fetchTracks();
  }, [genre, yearRange, favoritesOnly]);

  const clearFilters = () => {
    setGenre('');
    setYearRange(null);
    setFavoritesOnly(false);
  };

  return (
    <div>
      <div role="group" aria-label="Filters">
        <select
          value={genre}
          onChange={(e) => setGenre(e.target.value)}
          data-testid="genre-filter"
          aria-label="Filter by genre"
        >
          <option value="">All Genres</option>
          <option value="Rock">Rock</option>
          <option value="Pop">Pop</option>
          <option value="Jazz">Jazz</option>
        </select>

        <div>
          <label>
            <input
              type="number"
              placeholder="Year Min"
              onChange={(e) => {
                const val = parseInt(e.target.value);
                setYearRange(yearRange ? [val, yearRange[1]] : [val, 2025]);
              }}
              data-testid="year-min"
              aria-label="Minimum year"
            />
          </label>
          <label>
            <input
              type="number"
              placeholder="Year Max"
              onChange={(e) => {
                const val = parseInt(e.target.value);
                setYearRange(yearRange ? [yearRange[0], val] : [2000, val]);
              }}
              data-testid="year-max"
              aria-label="Maximum year"
            />
          </label>
        </div>

        <label>
          <input
            type="checkbox"
            checked={favoritesOnly}
            onChange={(e) => setFavoritesOnly(e.target.checked)}
            data-testid="favorites-filter"
            aria-label="Show favorites only"
          />
          Favorites Only
        </label>

        <button onClick={clearFilters} data-testid="clear-filters">
          Clear All Filters
        </button>
      </div>

      <div data-testid="filter-results" aria-live="polite">
        {tracks.length} tracks
      </div>
    </div>
  );
};

describe('Filter Combinations', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should filter by genre', async () => {
    // Arrange
    server.use(
      http.get('http://localhost:8765/api/library/tracks', ({ request }) => {
        const url = new URL(request.url);
        const genre = url.searchParams.get('genre');

        const mockTracks = [
          { id: 1, title: 'Rock Song', genre: 'Rock' },
          { id: 2, title: 'Pop Song', genre: 'Pop' },
          { id: 3, title: 'Jazz Song', genre: 'Jazz' },
        ];

        const filtered = genre
          ? mockTracks.filter(t => t.genre === genre)
          : mockTracks;

        return HttpResponse.json({
          tracks: filtered,
          total: filtered.length,
          has_more: false
        });
      })
    );

    // Act
    render(<FilterableLibrary />);

    await waitFor(() => {
      expect(screen.getByTestId('filter-results')).toHaveTextContent('3 tracks');
    });

    const genreFilter = screen.getByTestId('genre-filter');
    await userEvent.selectOptions(genreFilter, 'Rock');

    // Assert
    await waitFor(() => {
      expect(screen.getByTestId('filter-results')).toHaveTextContent('1 tracks');
    });
  });

  it('should filter by year range', async () => {
    // Arrange
    server.use(
      http.get('http://localhost:8765/api/library/tracks', ({ request }) => {
        const url = new URL(request.url);
        const yearMin = parseInt(url.searchParams.get('year_min') || '0');
        const yearMax = parseInt(url.searchParams.get('year_max') || '9999');

        const mockTracks = [
          { id: 1, title: 'Old Song', year: 1980 },
          { id: 2, title: 'Recent Song', year: 2020 },
          { id: 3, title: 'New Song', year: 2024 },
        ];

        const filtered = mockTracks.filter(t =>
          t.year >= yearMin && t.year <= yearMax
        );

        return HttpResponse.json({
          tracks: filtered,
          total: filtered.length,
          has_more: false
        });
      })
    );

    // Act
    render(<FilterableLibrary />);

    await waitFor(() => {
      expect(screen.getByTestId('filter-results')).toHaveTextContent('3 tracks');
    });

    const yearMin = screen.getByTestId('year-min');
    const yearMax = screen.getByTestId('year-max');

    await userEvent.type(yearMin, '2020');
    await userEvent.type(yearMax, '2024');

    // Assert
    await waitFor(() => {
      expect(screen.getByTestId('filter-results')).toHaveTextContent('2 tracks');
    });
  });

  it('should filter by favorite status', async () => {
    // Arrange
    server.use(
      http.get('http://localhost:8765/api/library/tracks', ({ request }) => {
        const url = new URL(request.url);
        const favoritesOnly = url.searchParams.get('favorites') === 'true';

        const mockTracks = [
          { id: 1, title: 'Favorite 1', favorite: true },
          { id: 2, title: 'Not Favorite', favorite: false },
          { id: 3, title: 'Favorite 2', favorite: true },
        ];

        const filtered = favoritesOnly
          ? mockTracks.filter(t => t.favorite)
          : mockTracks;

        return HttpResponse.json({
          tracks: filtered,
          total: filtered.length,
          has_more: false
        });
      })
    );

    // Act
    render(<FilterableLibrary />);

    await waitFor(() => {
      expect(screen.getByTestId('filter-results')).toHaveTextContent('3 tracks');
    });

    const favoritesFilter = screen.getByTestId('favorites-filter');
    await userEvent.click(favoritesFilter);

    // Assert
    await waitFor(() => {
      expect(screen.getByTestId('filter-results')).toHaveTextContent('2 tracks');
    });
  });

  it('should combine multiple filters (genre AND year)', async () => {
    // Arrange
    server.use(
      http.get('http://localhost:8765/api/library/tracks', ({ request }) => {
        const url = new URL(request.url);
        const genre = url.searchParams.get('genre');
        const yearMin = parseInt(url.searchParams.get('year_min') || '0');
        const yearMax = parseInt(url.searchParams.get('year_max') || '9999');

        const mockTracks = [
          { id: 1, title: 'Old Rock', genre: 'Rock', year: 1980 },
          { id: 2, title: 'New Rock', genre: 'Rock', year: 2020 },
          { id: 3, title: 'Old Pop', genre: 'Pop', year: 1980 },
          { id: 4, title: 'New Pop', genre: 'Pop', year: 2020 },
        ];

        let filtered = mockTracks;

        if (genre) {
          filtered = filtered.filter(t => t.genre === genre);
        }

        filtered = filtered.filter(t => t.year >= yearMin && t.year <= yearMax);

        return HttpResponse.json({
          tracks: filtered,
          total: filtered.length,
          has_more: false
        });
      })
    );

    // Act
    render(<FilterableLibrary />);

    await waitFor(() => {
      expect(screen.getByTestId('filter-results')).toHaveTextContent('4 tracks');
    });

    // Apply genre filter
    const genreFilter = screen.getByTestId('genre-filter');
    await userEvent.selectOptions(genreFilter, 'Rock');

    await waitFor(() => {
      expect(screen.getByTestId('filter-results')).toHaveTextContent('2 tracks');
    });

    // Apply year range filter
    const yearMin = screen.getByTestId('year-min');
    const yearMax = screen.getByTestId('year-max');
    await userEvent.type(yearMin, '2020');
    await userEvent.type(yearMax, '2024');

    // Assert - Should only show Rock tracks from 2020-2024
    await waitFor(() => {
      expect(screen.getByTestId('filter-results')).toHaveTextContent('1 tracks');
    });
  });

  it('should clear all filters', async () => {
    // Arrange
    server.use(
      http.get('http://localhost:8765/api/library/tracks', ({ request }) => {
        const url = new URL(request.url);
        const hasFilters = url.searchParams.has('genre') ||
                           url.searchParams.has('year_min') ||
                           url.searchParams.has('favorites');

        const mockTracks = Array.from({ length: 10 }, (_, i) => ({
          id: i + 1,
          title: `Track ${i + 1}`,
          genre: 'Rock',
          year: 2020,
          favorite: false
        }));

        return HttpResponse.json({
          tracks: hasFilters ? mockTracks.slice(0, 2) : mockTracks,
          total: hasFilters ? 2 : mockTracks.length,
          has_more: false
        });
      })
    );

    // Act
    render(<FilterableLibrary />);

    await waitFor(() => {
      expect(screen.getByTestId('filter-results')).toHaveTextContent('10 tracks');
    });

    // Apply filters
    const genreFilter = screen.getByTestId('genre-filter');
    await userEvent.selectOptions(genreFilter, 'Rock');

    await waitFor(() => {
      expect(screen.getByTestId('filter-results')).toHaveTextContent('2 tracks');
    });

    // Clear all filters
    const clearBtn = screen.getByTestId('clear-filters');
    await userEvent.click(clearBtn);

    // Assert - Should show all tracks again
    await waitFor(() => {
      expect(screen.getByTestId('filter-results')).toHaveTextContent('10 tracks');
    });
  });
});
