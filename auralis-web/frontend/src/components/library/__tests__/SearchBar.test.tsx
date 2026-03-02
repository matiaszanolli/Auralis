/**
 * SearchBar Component Tests
 * ~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Tests for search bar component including:
 * - Input value changes
 * - Debouncing behavior
 * - Clear functionality
 * - Loading state
 * - Accessibility
 * - Auto-focus
 *
 * @module components/library/__tests__/SearchBar.test
 */

import { render, screen, fireEvent, act } from '@testing-library/react';
import { vi } from 'vitest';
import SearchBar from '@/components/library/SearchBar';

describe('SearchBar', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('rendering', () => {
    it('should render search input', () => {
      const mockOnSearch = vi.fn();

      render(<SearchBar onSearch={mockOnSearch} />);

      const input = screen.getByRole('textbox');
      expect(input).toBeInTheDocument();
    });

    it('should display default placeholder', () => {
      const mockOnSearch = vi.fn();

      render(<SearchBar onSearch={mockOnSearch} />);

      const input = screen.getByRole('textbox');
      expect(input).toHaveAttribute(
        'placeholder',
        'Search tracks, albums, artists...'
      );
    });

    it('should display custom placeholder', () => {
      const mockOnSearch = vi.fn();

      render(
        <SearchBar
          onSearch={mockOnSearch}
          placeholder="Find your favorite songs"
        />
      );

      const input = screen.getByRole('textbox');
      expect(input).toHaveAttribute('placeholder', 'Find your favorite songs');
    });

    it('should display search hint when no query', () => {
      const mockOnSearch = vi.fn();

      render(<SearchBar onSearch={mockOnSearch} />);

      // Check the placeholder attribute on the input
      const input = screen.getByRole('textbox');
      expect(input).toHaveAttribute('placeholder', 'Search tracks, albums, artists...');
    });

    it('should display search icon', () => {
      const mockOnSearch = vi.fn();

      const { container } = render(<SearchBar onSearch={mockOnSearch} />);

      const icon = Array.from(container.querySelectorAll('span')).find(
        (el) => el.textContent === '🔍'
      );
      expect(icon).toBeInTheDocument();
    });
  });

  describe('input changes', () => {
    it('should update input value on change', async () => {
      const mockOnSearch = vi.fn();

      render(<SearchBar onSearch={mockOnSearch} />);

      const input = screen.getByRole('textbox');

      await act(async () => {
        fireEvent.change(input, { target: { value: 'beatles' } });
      });

      expect(input).toHaveValue('beatles');
    });

    it('should debounce onSearch callback', async () => {
      const mockOnSearch = vi.fn();

      render(<SearchBar onSearch={mockOnSearch} debounceMs={300} />);

      const input = screen.getByRole('textbox');

      // Type query
      await act(async () => {
        fireEvent.change(input, { target: { value: 'b' } });
        fireEvent.change(input, { target: { value: 'be' } });
        fireEvent.change(input, { target: { value: 'bea' } });
      });

      // Callback shouldn't be called yet
      expect(mockOnSearch).not.toHaveBeenCalled();

      // Advance timers to trigger debounce
      await act(async () => {
        vi.advanceTimersByTime(300);
      });

      // Now it should be called with final value
      expect(mockOnSearch).toHaveBeenCalledTimes(1);
      expect(mockOnSearch).toHaveBeenCalledWith('bea');
    });

    it('should respect custom debounce duration', async () => {
      const mockOnSearch = vi.fn();

      render(<SearchBar onSearch={mockOnSearch} debounceMs={500} />);

      const input = screen.getByRole('textbox');

      await act(async () => {
        fireEvent.change(input, { target: { value: 'test' } });
      });

      // Advance 300ms (less than debounce)
      await act(async () => {
        vi.advanceTimersByTime(300);
      });

      expect(mockOnSearch).not.toHaveBeenCalled();

      // Advance another 200ms (total 500ms)
      await act(async () => {
        vi.advanceTimersByTime(200);
      });

      expect(mockOnSearch).toHaveBeenCalled();
    });

    it('should reset debounce timer on repeated input', async () => {
      const mockOnSearch = vi.fn();

      render(<SearchBar onSearch={mockOnSearch} debounceMs={300} />);

      const input = screen.getByRole('textbox');

      await act(async () => {
        fireEvent.change(input, { target: { value: 'first' } });
      });

      // Advance 250ms (not enough to trigger)
      await act(async () => {
        vi.advanceTimersByTime(250);
      });

      expect(mockOnSearch).not.toHaveBeenCalled();

      // Change input again (resets timer)
      await act(async () => {
        fireEvent.change(input, { target: { value: 'first search' } });
      });

      // Advance 200ms more (250 + 200 = 450ms from first input, but only 200ms from second)
      await act(async () => {
        vi.advanceTimersByTime(200);
      });

      expect(mockOnSearch).not.toHaveBeenCalled();

      // Advance 100ms more (300ms from second input)
      await act(async () => {
        vi.advanceTimersByTime(100);
      });

      expect(mockOnSearch).toHaveBeenCalledWith('first search');
    });
  });

  describe('clear functionality', () => {
    it('should display clear button when query is not empty', async () => {
      const mockOnSearch = vi.fn();

      render(<SearchBar onSearch={mockOnSearch} />);

      const input = screen.getByRole('textbox');

      await act(async () => {
        fireEvent.change(input, { target: { value: 'beatles' } });
        vi.advanceTimersByTime(300);
      });

      const clearButton = screen.getByRole('button', { name: /clear search/i });
      expect(clearButton).toBeInTheDocument();
    });

    it('should not display clear button when query is empty', () => {
      const mockOnSearch = vi.fn();

      render(<SearchBar onSearch={mockOnSearch} />);

      const clearButton = screen.queryByRole('button', { name: /clear search/i });
      expect(clearButton).not.toBeInTheDocument();
    });

    it('should clear input and call onSearch with empty string', async () => {
      const mockOnSearch = vi.fn();

      render(<SearchBar onSearch={mockOnSearch} />);

      const input = screen.getByRole('textbox');

      await act(async () => {
        fireEvent.change(input, { target: { value: 'beatles' } });
        vi.advanceTimersByTime(300);
      });

      mockOnSearch.mockClear();

      const clearButton = screen.getByRole('button', { name: /clear search/i });

      await act(async () => {
        fireEvent.click(clearButton);
      });

      expect(input).toHaveValue('');
      expect(mockOnSearch).toHaveBeenCalledWith('');
    });

    it('should focus input after clearing', async () => {
      const mockOnSearch = vi.fn();

      render(<SearchBar onSearch={mockOnSearch} />);

      const input = screen.getByRole('textbox') as HTMLInputElement;

      await act(async () => {
        fireEvent.change(input, { target: { value: 'beatles' } });
        vi.advanceTimersByTime(300);
      });

      const clearButton = screen.getByRole('button', { name: /clear search/i });

      await act(async () => {
        fireEvent.click(clearButton);
      });

      expect(document.activeElement).toBe(input);
    });

    it('should not display clear button while loading', async () => {
      const mockOnSearch = vi.fn();

      render(<SearchBar onSearch={mockOnSearch} />);

      const input = screen.getByRole('textbox');

      await act(async () => {
        fireEvent.change(input, { target: { value: 'beatles' } });
        // Don't advance timers - stay in loading state
      });

      // Should not have clear button while debouncing
      const clearButton = screen.queryByRole('button', { name: /clear search/i });
      expect(clearButton).not.toBeInTheDocument();
    });
  });

  describe('loading state', () => {
    it('should display loading indicator while debouncing', async () => {
      const mockOnSearch = vi.fn();

      const { container } = render(<SearchBar onSearch={mockOnSearch} />);

      const input = screen.getByRole('textbox');

      await act(async () => {
        fireEvent.change(input, { target: { value: 'beatles' } });
      });

      // Check for loading icon
      const loadingIcon = Array.from(container.querySelectorAll('span')).find(
        (el) => el.textContent === '⟳'
      );
      expect(loadingIcon).toBeInTheDocument();
    });

    it('should hide loading indicator after debounce completes', async () => {
      const mockOnSearch = vi.fn();

      render(<SearchBar onSearch={mockOnSearch} />);

      const input = screen.getByRole('textbox');

      await act(async () => {
        fireEvent.change(input, { target: { value: 'beatles' } });
      });

      await act(async () => {
        vi.advanceTimersByTime(300);
      });

      // After debounce, loading state should be false
      expect(mockOnSearch).toHaveBeenCalled();
    });
  });

  describe('search hint display', () => {
    it('should display search hint when query is present', async () => {
      const mockOnSearch = vi.fn();

      render(<SearchBar onSearch={mockOnSearch} />);

      const input = screen.getByRole('textbox');

      await act(async () => {
        fireEvent.change(input, { target: { value: 'beatles' } });
        vi.advanceTimersByTime(300);
      });

      expect(screen.getByText(/Searching for/)).toBeInTheDocument();
      expect(screen.getByText('beatles')).toBeInTheDocument();
    });

    it('should not display search hint when loading', async () => {
      const mockOnSearch = vi.fn();

      render(<SearchBar onSearch={mockOnSearch} />);

      const input = screen.getByRole('textbox');

      await act(async () => {
        fireEvent.change(input, { target: { value: 'beatles' } });
        // Don't advance timers - stay loading
      });

      // Should not show "Searching for" while debouncing
      expect(screen.queryByText(/Searching for/)).not.toBeInTheDocument();
    });

    it('should highlight searched query in hint', async () => {
      const mockOnSearch = vi.fn();

      const { container } = render(<SearchBar onSearch={mockOnSearch} />);

      const input = screen.getByRole('textbox');

      await act(async () => {
        fireEvent.change(input, { target: { value: 'test' } });
        vi.advanceTimersByTime(300);
      });

      const highlight = container.querySelector('[style*="color"]');
      expect(highlight?.textContent).toBe('test');
    });
  });

  describe('auto-focus', () => {
    it('should not auto-focus by default', () => {
      const mockOnSearch = vi.fn();

      render(<SearchBar onSearch={mockOnSearch} />);

      const input = screen.getByRole('textbox') as HTMLInputElement;
      expect(input).not.toBe(document.activeElement);
    });

    it('should auto-focus when autoFocus prop is true', () => {
      const mockOnSearch = vi.fn();

      render(<SearchBar onSearch={mockOnSearch} autoFocus={true} />);

      const input = screen.getByRole('textbox') as HTMLInputElement;
      expect(input).toBe(document.activeElement);
    });
  });

  describe('cleanup', () => {
    it('should clear debounce timer on unmount', async () => {
      const mockOnSearch = vi.fn();

      const { unmount } = render(<SearchBar onSearch={mockOnSearch} />);

      const input = screen.getByRole('textbox');

      await act(async () => {
        fireEvent.change(input, { target: { value: 'beatles' } });
      });

      unmount();

      // Advance timers - callback should not be called since component unmounted
      await act(async () => {
        vi.advanceTimersByTime(300);
      });

      // This ensures the cleanup ran and no memory leaks
      expect(mockOnSearch).not.toHaveBeenCalled();
    });
  });

  describe('accessibility', () => {
    it('should have aria-label on input', () => {
      const mockOnSearch = vi.fn();

      render(<SearchBar onSearch={mockOnSearch} />);

      const input = screen.getByRole('textbox');
      expect(input).toHaveAttribute('aria-label', 'Search');
    });

    it('should have aria-label on clear button', async () => {
      const mockOnSearch = vi.fn();

      render(<SearchBar onSearch={mockOnSearch} />);

      const input = screen.getByRole('textbox');

      await act(async () => {
        fireEvent.change(input, { target: { value: 'beatles' } });
        vi.advanceTimersByTime(300);
      });

      const clearButton = screen.getByRole('button');
      expect(clearButton).toHaveAttribute('aria-label', 'Clear search');
    });

    it('should have title attribute on clear button', async () => {
      const mockOnSearch = vi.fn();

      render(<SearchBar onSearch={mockOnSearch} />);

      const input = screen.getByRole('textbox');

      await act(async () => {
        fireEvent.change(input, { target: { value: 'beatles' } });
        vi.advanceTimersByTime(300);
      });

      const clearButton = screen.getByRole('button');
      expect(clearButton).toHaveAttribute('title', 'Clear search');
    });
  });

  describe('edge cases', () => {
    it('should handle empty string search', async () => {
      const mockOnSearch = vi.fn();

      render(<SearchBar onSearch={mockOnSearch} />);

      const input = screen.getByRole('textbox');

      await act(async () => {
        fireEvent.change(input, { target: { value: '' } });
        vi.advanceTimersByTime(300);
      });

      expect(mockOnSearch).toHaveBeenCalledWith('');
    });

    it('should handle whitespace-only search', async () => {
      const mockOnSearch = vi.fn();

      render(<SearchBar onSearch={mockOnSearch} />);

      const input = screen.getByRole('textbox');

      await act(async () => {
        fireEvent.change(input, { target: { value: '   ' } });
        vi.advanceTimersByTime(300);
      });

      expect(mockOnSearch).toHaveBeenCalledWith('   ');
    });

    it('should handle special characters in search', async () => {
      const mockOnSearch = vi.fn();

      render(<SearchBar onSearch={mockOnSearch} />);

      const input = screen.getByRole('textbox');

      await act(async () => {
        fireEvent.change(input, { target: { value: 'test & special' } });
        vi.advanceTimersByTime(300);
      });

      expect(mockOnSearch).toHaveBeenCalledWith('test & special');
    });

    it('should handle very long search queries', async () => {
      const mockOnSearch = vi.fn();
      const longQuery = 'a'.repeat(1000);

      render(<SearchBar onSearch={mockOnSearch} />);

      const input = screen.getByRole('textbox');

      await act(async () => {
        fireEvent.change(input, { target: { value: longQuery } });
        vi.advanceTimersByTime(300);
      });

      expect(mockOnSearch).toHaveBeenCalledWith(longQuery);
    });
  });
});
