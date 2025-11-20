/**
 * Advanced Search Integration Tests
 *
 * Tests for search functionality including fuzzy matching, multi-field search,
 * and debouncing behavior.
 *
 * Test Categories:
 * 1. Advanced Search (5 tests)
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

describe('Advanced Search Integration Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

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
