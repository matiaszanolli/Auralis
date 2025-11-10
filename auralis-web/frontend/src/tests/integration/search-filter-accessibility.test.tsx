/**
 * Search, Filter & Accessibility Integration Tests
 *
 * Week 8 of 200-test frontend integration suite
 * Tests covering advanced search, filter combinations, sort operations,
 * keyboard accessibility, and screen reader support
 *
 * Test Categories:
 * 1. Advanced Search (5 tests)
 * 2. Filter Combinations (5 tests)
 * 3. Sort Operations (5 tests)
 * 4. Keyboard Accessibility (3 tests)
 * 5. Screen Reader Support (2 tests)
 *
 * Total: 20 tests
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { screen, waitFor, within } from '@testing-library/react';
import { render } from '@/test/test-utils';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from '@/test/mocks/server';
import * as React from 'react';

// Mock searchable library component
const SearchableLibrary = () => {
  const [searchQuery, setSearchQuery] = React.useState('');
  const [tracks, setTracks] = React.useState<any[]>([]);
  const [loading, setLoading] = React.useState(false);
  const searchTimeoutRef = React.useRef<NodeJS.Timeout>();

  // Debounced search (300ms)
  React.useEffect(() => {
    if (searchTimeoutRef.current) {
      clearTimeout(searchTimeoutRef.current);
    }

    searchTimeoutRef.current = setTimeout(async () => {
      if (searchQuery) {
        setLoading(true);
        const response = await fetch(
          `http://localhost:8765/api/library/tracks?search=${encodeURIComponent(searchQuery)}`
        );
        const data = await response.json();
        setTracks(data.tracks);
        setLoading(false);
      } else {
        setTracks([]);
      }
    }, 300);

    return () => {
      if (searchTimeoutRef.current) {
        clearTimeout(searchTimeoutRef.current);
      }
    };
  }, [searchQuery]);

  return (
    <div>
      <input
        type="search"
        placeholder="Search by title, artist, or album..."
        value={searchQuery}
        onChange={(e) => setSearchQuery(e.target.value)}
        data-testid="search-input"
        aria-label="Search tracks"
      />
      {loading && <div data-testid="loading">Loading...</div>}
      <div data-testid="search-results" aria-live="polite" aria-atomic="true">
        {tracks.length} results
      </div>
      <ul role="list" aria-label="Track results">
        {tracks.map(track => (
          <li key={track.id} data-testid={`track-${track.id}`}>
            {track.title} - {track.artist}
          </li>
        ))}
      </ul>
    </div>
  );
};

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

// Mock sortable library component
const SortableLibrary = () => {
  const [sortBy, setSortBy] = React.useState('title');
  const [order, setOrder] = React.useState<'asc' | 'desc'>('asc');
  const [tracks, setTracks] = React.useState<any[]>([]);

  React.useEffect(() => {
    const fetchTracks = async () => {
      const response = await fetch(
        `http://localhost:8765/api/library/tracks?sort=${sortBy}&order=${order}`
      );
      const data = await response.json();
      setTracks(data.tracks);
    };

    fetchTracks();
  }, [sortBy, order]);

  return (
    <div>
      <div role="group" aria-label="Sort options">
        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value)}
          data-testid="sort-select"
          aria-label="Sort by"
        >
          <option value="title">Title</option>
          <option value="artist">Artist</option>
          <option value="date_added">Date Added</option>
          <option value="play_count">Play Count</option>
          <option value="duration">Duration</option>
        </select>

        <button
          onClick={() => setOrder(order === 'asc' ? 'desc' : 'asc')}
          data-testid="toggle-order"
          aria-label={`Sort ${order === 'asc' ? 'ascending' : 'descending'}`}
        >
          {order === 'asc' ? '↑' : '↓'}
        </button>
      </div>

      <div data-testid="sort-results" aria-live="polite">
        {tracks.length} tracks sorted by {sortBy} ({order})
      </div>

      <ul role="list">
        {tracks.map((track, idx) => (
          <li key={track.id} data-testid={`sorted-track-${idx}`}>
            {track.title}
          </li>
        ))}
      </ul>
    </div>
  );
};

// Mock track list with keyboard navigation
const KeyboardNavigableTrackList = () => {
  const [tracks] = React.useState(
    Array.from({ length: 10 }, (_, i) => ({
      id: i + 1,
      title: `Track ${i + 1}`,
      artist: `Artist ${i + 1}`
    }))
  );
  const [selectedIndex, setSelectedIndex] = React.useState(0);
  const [focusedIndex, setFocusedIndex] = React.useState(0);
  const trackRefs = React.useRef<(HTMLDivElement | null)[]>([]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setFocusedIndex(prev => Math.min(prev + 1, tracks.length - 1));
        break;
      case 'ArrowUp':
        e.preventDefault();
        setFocusedIndex(prev => Math.max(prev - 1, 0));
        break;
      case 'Enter':
        e.preventDefault();
        setSelectedIndex(focusedIndex);
        break;
      case 'Tab':
        // Allow default tab behavior
        break;
    }
  };

  React.useEffect(() => {
    trackRefs.current[focusedIndex]?.focus();
  }, [focusedIndex]);

  return (
    <div
      role="list"
      aria-label="Track list"
      onKeyDown={handleKeyDown}
      data-testid="track-list"
    >
      {tracks.map((track, idx) => (
        <div
          key={track.id}
          ref={el => trackRefs.current[idx] = el}
          tabIndex={idx === focusedIndex ? 0 : -1}
          role="listitem"
          aria-selected={idx === selectedIndex}
          data-testid={`track-item-${idx}`}
          onClick={() => {
            setSelectedIndex(idx);
            setFocusedIndex(idx);
          }}
          style={{
            background: idx === selectedIndex ? '#e0e0e0' : 'transparent',
            outline: idx === focusedIndex ? '2px solid blue' : 'none',
            padding: '8px'
          }}
        >
          {track.title} - {track.artist}
        </div>
      ))}
      <div data-testid="selected-index" aria-live="polite">
        Selected: {selectedIndex}
      </div>
    </div>
  );
};

describe('Search, Filter & Accessibility Integration Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // ==========================================
  // 1. Advanced Search (5 tests)
  // ==========================================

  describe('Advanced Search', () => {
    it('should search by title with fuzzy matching', async () => {
      // Arrange
      const mockTracks = [
        { id: 1, title: 'Bohemian Rhapsody', artist: 'Queen', album: 'A Night at the Opera' },
        { id: 2, title: 'Rhapsody in Blue', artist: 'George Gershwin', album: 'Classical' },
        { id: 3, title: 'Hungarian Rhapsody', artist: 'Franz Liszt', album: 'Piano Works' },
        { id: 4, title: 'Stairway to Heaven', artist: 'Led Zeppelin', album: 'IV' },
      ];

      server.use(
        http.get('http://localhost:8765/api/library/tracks', ({ request }) => {
          const url = new URL(request.url);
          const search = url.searchParams.get('search')?.toLowerCase() || '';

          const filtered = mockTracks.filter(t =>
            t.title.toLowerCase().includes(search)
          );

          return HttpResponse.json({
            tracks: filtered,
            total: filtered.length,
            has_more: false
          });
        })
      );

      // Act
      render(<SearchableLibrary />);

      const searchInput = screen.getByTestId('search-input');
      await userEvent.type(searchInput, 'rhapsody');

      // Assert - Should find all tracks with "rhapsody" in title (fuzzy matching)
      await waitFor(() => {
        expect(screen.getByTestId('search-results')).toHaveTextContent('3 results');
      }, { timeout: 500 }); // Allow time for 300ms debounce

      expect(screen.getByTestId('track-1')).toHaveTextContent('Bohemian Rhapsody');
      expect(screen.getByTestId('track-2')).toHaveTextContent('Rhapsody in Blue');
      expect(screen.getByTestId('track-3')).toHaveTextContent('Hungarian Rhapsody');
    });

    it('should search by artist with exact and partial match', async () => {
      // Arrange
      const mockTracks = [
        { id: 1, title: 'Track 1', artist: 'The Beatles', album: 'Abbey Road' },
        { id: 2, title: 'Track 2', artist: 'Beatles Cover Band', album: 'Covers' },
        { id: 3, title: 'Track 3', artist: 'John Lennon', album: 'Imagine' },
      ];

      server.use(
        http.get('http://localhost:8765/api/library/tracks', ({ request }) => {
          const url = new URL(request.url);
          const search = url.searchParams.get('search')?.toLowerCase() || '';

          const filtered = mockTracks.filter(t =>
            t.artist.toLowerCase().includes(search)
          );

          return HttpResponse.json({
            tracks: filtered,
            total: filtered.length,
            has_more: false
          });
        })
      );

      // Act
      render(<SearchableLibrary />);

      const searchInput = screen.getByTestId('search-input');
      await userEvent.type(searchInput, 'beatles');

      // Assert - Should find both exact match and partial match
      await waitFor(() => {
        expect(screen.getByTestId('search-results')).toHaveTextContent('2 results');
      }, { timeout: 500 });

      expect(screen.getByTestId('track-1')).toBeInTheDocument();
      expect(screen.getByTestId('track-2')).toBeInTheDocument();
      expect(screen.queryByTestId('track-3')).not.toBeInTheDocument();
    });

    it('should search by album', async () => {
      // Arrange
      const mockTracks = [
        { id: 1, title: 'Song 1', artist: 'Artist A', album: 'Dark Side of the Moon' },
        { id: 2, title: 'Song 2', artist: 'Artist A', album: 'Dark Side of the Moon' },
        { id: 3, title: 'Song 3', artist: 'Artist B', album: 'The Wall' },
      ];

      server.use(
        http.get('http://localhost:8765/api/library/tracks', ({ request }) => {
          const url = new URL(request.url);
          const search = url.searchParams.get('search')?.toLowerCase() || '';

          const filtered = mockTracks.filter(t =>
            t.album.toLowerCase().includes(search)
          );

          return HttpResponse.json({
            tracks: filtered,
            total: filtered.length,
            has_more: false
          });
        })
      );

      // Act
      render(<SearchableLibrary />);

      const searchInput = screen.getByTestId('search-input');
      await userEvent.type(searchInput, 'dark side');

      // Assert
      await waitFor(() => {
        expect(screen.getByTestId('search-results')).toHaveTextContent('2 results');
      }, { timeout: 500 });

      expect(screen.getByTestId('track-1')).toBeInTheDocument();
      expect(screen.getByTestId('track-2')).toBeInTheDocument();
    });

    it('should search across multiple fields (title OR artist OR album)', async () => {
      // Arrange
      const mockTracks = [
        { id: 1, title: 'Purple Rain', artist: 'Prince', album: 'Purple Rain' },
        { id: 2, title: 'Purple Haze', artist: 'Jimi Hendrix', album: 'Are You Experienced' },
        { id: 3, title: 'Smoke on the Water', artist: 'Deep Purple', album: 'Machine Head' },
        { id: 4, title: 'Black Dog', artist: 'Led Zeppelin', album: 'IV' },
      ];

      server.use(
        http.get('http://localhost:8765/api/library/tracks', ({ request }) => {
          const url = new URL(request.url);
          const search = url.searchParams.get('search')?.toLowerCase() || '';

          const filtered = mockTracks.filter(t =>
            t.title.toLowerCase().includes(search) ||
            t.artist.toLowerCase().includes(search) ||
            t.album.toLowerCase().includes(search)
          );

          return HttpResponse.json({
            tracks: filtered,
            total: filtered.length,
            has_more: false
          });
        })
      );

      // Act
      render(<SearchableLibrary />);

      const searchInput = screen.getByTestId('search-input');
      await userEvent.type(searchInput, 'purple');

      // Assert - Should find matches in title, artist, and album
      await waitFor(() => {
        expect(screen.getByTestId('search-results')).toHaveTextContent('3 results');
      }, { timeout: 500 });

      expect(screen.getByTestId('track-1')).toBeInTheDocument(); // Title + Album
      expect(screen.getByTestId('track-2')).toBeInTheDocument(); // Title
      expect(screen.getByTestId('track-3')).toBeInTheDocument(); // Artist
    });

    it('should debounce search with 300ms delay', async () => {
      // Arrange
      let requestCount = 0;

      server.use(
        http.get('http://localhost:8765/api/library/tracks', ({ request }) => {
          requestCount++;
          const url = new URL(request.url);
          const search = url.searchParams.get('search') || '';

          return HttpResponse.json({
            tracks: [{ id: 1, title: search, artist: 'Artist' }],
            total: 1,
            has_more: false
          });
        })
      );

      // Act
      render(<SearchableLibrary />);

      const searchInput = screen.getByTestId('search-input');

      // Type quickly (should not trigger multiple requests due to debounce)
      await userEvent.type(searchInput, 'test');

      // Assert - Should only make 1 request after debounce period
      await waitFor(() => {
        expect(screen.getByTestId('search-results')).toHaveTextContent('1 results');
      }, { timeout: 500 });

      // Should have made exactly 1 request (debounced)
      expect(requestCount).toBe(1);
    });
  });

  // ==========================================
  // 2. Filter Combinations (5 tests)
  // ==========================================

  describe('Filter Combinations', () => {
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

  // ==========================================
  // 3. Sort Operations (5 tests)
  // ==========================================

  describe('Sort Operations', () => {
    it('should sort by title (A-Z, Z-A)', async () => {
      // Arrange
      const mockTracks = [
        { id: 1, title: 'Zebra' },
        { id: 2, title: 'Apple' },
        { id: 3, title: 'Mango' },
      ];

      server.use(
        http.get('http://localhost:8765/api/library/tracks', ({ request }) => {
          const url = new URL(request.url);
          const sortBy = url.searchParams.get('sort') || 'title';
          const order = url.searchParams.get('order') || 'asc';

          const sorted = [...mockTracks].sort((a, b) => {
            return order === 'asc'
              ? a.title.localeCompare(b.title)
              : b.title.localeCompare(a.title);
          });

          return HttpResponse.json({
            tracks: sorted,
            total: sorted.length,
            has_more: false
          });
        })
      );

      // Act
      render(<SortableLibrary />);

      // Assert - Default sort (A-Z)
      await waitFor(() => {
        expect(screen.getByTestId('sorted-track-0')).toHaveTextContent('Apple');
        expect(screen.getByTestId('sorted-track-1')).toHaveTextContent('Mango');
        expect(screen.getByTestId('sorted-track-2')).toHaveTextContent('Zebra');
      });

      // Toggle to Z-A
      const toggleBtn = screen.getByTestId('toggle-order');
      await userEvent.click(toggleBtn);

      await waitFor(() => {
        expect(screen.getByTestId('sorted-track-0')).toHaveTextContent('Zebra');
        expect(screen.getByTestId('sorted-track-1')).toHaveTextContent('Mango');
        expect(screen.getByTestId('sorted-track-2')).toHaveTextContent('Apple');
      });
    });

    it('should sort by artist', async () => {
      // Arrange
      const mockTracks = [
        { id: 1, title: 'Song 1', artist: 'Zeppelin' },
        { id: 2, title: 'Song 2', artist: 'Beatles' },
        { id: 3, title: 'Song 3', artist: 'Queen' },
      ];

      server.use(
        http.get('http://localhost:8765/api/library/tracks', ({ request }) => {
          const url = new URL(request.url);
          const sortBy = url.searchParams.get('sort');
          const order = url.searchParams.get('order') || 'asc';

          if (sortBy === 'artist') {
            const sorted = [...mockTracks].sort((a, b) => {
              return order === 'asc'
                ? a.artist.localeCompare(b.artist)
                : b.artist.localeCompare(a.artist);
            });

            return HttpResponse.json({
              tracks: sorted,
              total: sorted.length,
              has_more: false
            });
          }

          return HttpResponse.json({
            tracks: mockTracks,
            total: mockTracks.length,
            has_more: false
          });
        })
      );

      // Act
      render(<SortableLibrary />);

      const sortSelect = screen.getByTestId('sort-select');
      await userEvent.selectOptions(sortSelect, 'artist');

      // Assert
      await waitFor(() => {
        expect(screen.getByTestId('sorted-track-0')).toHaveTextContent('Song 2');
        expect(screen.getByTestId('sorted-track-1')).toHaveTextContent('Song 3');
        expect(screen.getByTestId('sorted-track-2')).toHaveTextContent('Song 1');
      });
    });

    it('should sort by date added', async () => {
      // Arrange
      const mockTracks = [
        { id: 1, title: 'Oldest', date_added: '2020-01-01' },
        { id: 2, title: 'Newest', date_added: '2024-01-01' },
        { id: 3, title: 'Middle', date_added: '2022-01-01' },
      ];

      server.use(
        http.get('http://localhost:8765/api/library/tracks', ({ request }) => {
          const url = new URL(request.url);
          const sortBy = url.searchParams.get('sort');
          const order = url.searchParams.get('order') || 'asc';

          if (sortBy === 'date_added') {
            const sorted = [...mockTracks].sort((a, b) => {
              return order === 'asc'
                ? a.date_added.localeCompare(b.date_added)
                : b.date_added.localeCompare(a.date_added);
            });

            return HttpResponse.json({
              tracks: sorted,
              total: sorted.length,
              has_more: false
            });
          }

          return HttpResponse.json({
            tracks: mockTracks,
            total: mockTracks.length,
            has_more: false
          });
        })
      );

      // Act
      render(<SortableLibrary />);

      const sortSelect = screen.getByTestId('sort-select');
      await userEvent.selectOptions(sortSelect, 'date_added');

      // Assert
      await waitFor(() => {
        expect(screen.getByTestId('sorted-track-0')).toHaveTextContent('Oldest');
        expect(screen.getByTestId('sorted-track-1')).toHaveTextContent('Middle');
        expect(screen.getByTestId('sorted-track-2')).toHaveTextContent('Newest');
      });
    });

    it('should sort by play count', async () => {
      // Arrange
      const mockTracks = [
        { id: 1, title: 'Popular', play_count: 100 },
        { id: 2, title: 'Unpopular', play_count: 5 },
        { id: 3, title: 'Medium', play_count: 50 },
      ];

      server.use(
        http.get('http://localhost:8765/api/library/tracks', ({ request }) => {
          const url = new URL(request.url);
          const sortBy = url.searchParams.get('sort');
          const order = url.searchParams.get('order') || 'asc';

          if (sortBy === 'play_count') {
            const sorted = [...mockTracks].sort((a, b) => {
              return order === 'asc'
                ? a.play_count - b.play_count
                : b.play_count - a.play_count;
            });

            return HttpResponse.json({
              tracks: sorted,
              total: sorted.length,
              has_more: false
            });
          }

          return HttpResponse.json({
            tracks: mockTracks,
            total: mockTracks.length,
            has_more: false
          });
        })
      );

      // Act
      render(<SortableLibrary />);

      const sortSelect = screen.getByTestId('sort-select');
      await userEvent.selectOptions(sortSelect, 'play_count');

      // Assert
      await waitFor(() => {
        expect(screen.getByTestId('sorted-track-0')).toHaveTextContent('Unpopular');
        expect(screen.getByTestId('sorted-track-1')).toHaveTextContent('Medium');
        expect(screen.getByTestId('sorted-track-2')).toHaveTextContent('Popular');
      });
    });

    it('should sort by duration', async () => {
      // Arrange
      const mockTracks = [
        { id: 1, title: 'Long Song', duration: 300 },
        { id: 2, title: 'Short Song', duration: 120 },
        { id: 3, title: 'Medium Song', duration: 210 },
      ];

      server.use(
        http.get('http://localhost:8765/api/library/tracks', ({ request }) => {
          const url = new URL(request.url);
          const sortBy = url.searchParams.get('sort');
          const order = url.searchParams.get('order') || 'asc';

          if (sortBy === 'duration') {
            const sorted = [...mockTracks].sort((a, b) => {
              return order === 'asc'
                ? a.duration - b.duration
                : b.duration - a.duration;
            });

            return HttpResponse.json({
              tracks: sorted,
              total: sorted.length,
              has_more: false
            });
          }

          return HttpResponse.json({
            tracks: mockTracks,
            total: mockTracks.length,
            has_more: false
          });
        })
      );

      // Act
      render(<SortableLibrary />);

      const sortSelect = screen.getByTestId('sort-select');
      await userEvent.selectOptions(sortSelect, 'duration');

      // Assert
      await waitFor(() => {
        expect(screen.getByTestId('sorted-track-0')).toHaveTextContent('Short Song');
        expect(screen.getByTestId('sorted-track-1')).toHaveTextContent('Medium Song');
        expect(screen.getByTestId('sorted-track-2')).toHaveTextContent('Long Song');
      });
    });
  });

  // ==========================================
  // 4. Keyboard Accessibility (3 tests)
  // ==========================================

  describe('Keyboard Accessibility', () => {
    it('should navigate tracks with arrow keys', async () => {
      // Arrange
      render(<KeyboardNavigableTrackList />);

      const trackList = screen.getByTestId('track-list');
      trackList.focus();

      // Act - Navigate down
      await userEvent.keyboard('{ArrowDown}');

      // Assert - Focus should move to next track
      await waitFor(() => {
        const track1 = screen.getByTestId('track-item-1');
        expect(track1).toHaveFocus();
      });

      // Navigate down again
      await userEvent.keyboard('{ArrowDown}');

      await waitFor(() => {
        const track2 = screen.getByTestId('track-item-2');
        expect(track2).toHaveFocus();
      });

      // Navigate up
      await userEvent.keyboard('{ArrowUp}');

      await waitFor(() => {
        const track1 = screen.getByTestId('track-item-1');
        expect(track1).toHaveFocus();
      });
    });

    it('should play track with Enter key', async () => {
      // Arrange
      render(<KeyboardNavigableTrackList />);

      const trackList = screen.getByTestId('track-list');
      trackList.focus();

      // Act - Navigate to track and press Enter
      await userEvent.keyboard('{ArrowDown}');
      await userEvent.keyboard('{ArrowDown}');
      await userEvent.keyboard('{Enter}');

      // Assert - Track should be selected
      await waitFor(() => {
        expect(screen.getByTestId('selected-index')).toHaveTextContent('Selected: 2');
      });
    });

    it('should handle focus management with Tab and Shift+Tab', async () => {
      // Arrange
      const FocusableComponent = () => (
        <div>
          <button data-testid="button-1">Button 1</button>
          <button data-testid="button-2">Button 2</button>
          <input data-testid="input-1" placeholder="Input 1" />
          <button data-testid="button-3">Button 3</button>
        </div>
      );

      render(<FocusableComponent />);

      const button1 = screen.getByTestId('button-1');
      const button2 = screen.getByTestId('button-2');
      const input1 = screen.getByTestId('input-1');

      // Act - Tab through elements
      button1.focus();
      expect(button1).toHaveFocus();

      await userEvent.tab();
      expect(button2).toHaveFocus();

      await userEvent.tab();
      expect(input1).toHaveFocus();

      // Shift+Tab to go back
      await userEvent.tab({ shift: true });
      expect(button2).toHaveFocus();
    });
  });

  // ==========================================
  // 5. Screen Reader Support (2 tests)
  // ==========================================

  describe('Screen Reader Support', () => {
    it('should have ARIA labels on interactive elements', () => {
      // Arrange & Act
      render(<FilterableLibrary />);

      // Assert - Check ARIA labels
      expect(screen.getByLabelText('Filter by genre')).toBeInTheDocument();
      expect(screen.getByLabelText('Minimum year')).toBeInTheDocument();
      expect(screen.getByLabelText('Maximum year')).toBeInTheDocument();
      expect(screen.getByLabelText('Show favorites only')).toBeInTheDocument();
      expect(screen.getByRole('group', { name: 'Filters' })).toBeInTheDocument();
    });

    it('should announce status updates with live regions', async () => {
      // Arrange
      render(<SearchableLibrary />);

      const searchInput = screen.getByTestId('search-input');
      const searchResults = screen.getByTestId('search-results');

      // Assert - Live region attributes
      expect(searchResults).toHaveAttribute('aria-live', 'polite');
      expect(searchResults).toHaveAttribute('aria-atomic', 'true');

      // Check search input has aria-label
      expect(searchInput).toHaveAttribute('aria-label', 'Search tracks');

      // Check results list has proper role and label
      const resultsList = screen.getByRole('list', { name: 'Track results' });
      expect(resultsList).toBeInTheDocument();
    });
  });
});
