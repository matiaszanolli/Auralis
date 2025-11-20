/**
 * Keyboard Accessibility & Screen Reader Support Integration Tests
 *
 * Tests for keyboard navigation, focus management, ARIA labels, and screen reader support.
 *
 * Test Categories:
 * 1. Keyboard Accessibility (3 tests)
 * 2. Screen Reader Support (2 tests)
 *
 * Previously part of search-filter-accessibility.test.tsx
 */

import { describe, it, expect } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import { render } from '@/test/test-utils';
import userEvent from '@testing-library/user-event';
import * as React from 'react';

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

// Mock filterable library component for screen reader tests
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
      </div>

      <div data-testid="filter-results" aria-live="polite">
        {tracks.length} tracks
      </div>
    </div>
  );
};

// Mock searchable library component for screen reader tests
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

describe('Accessibility Integration Tests', () => {
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
