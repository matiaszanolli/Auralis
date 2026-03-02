/**
 * Sort Integration Tests
 *
 * Tests for sorting functionality including title, artist, date added, play count, and duration.
 *
 * Test Categories:
 * 1. Sort Operations (5 tests)
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

describe('Sort Operations', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

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
