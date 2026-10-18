/**
 * GlobalSearch Component Tests
 *
 * Simplified test suite focusing on core functionality:
 * - Rendering the search input
 * - Basic input interaction
 * - Component initialization
 */

import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import { render, screen } from '@/test/test-utils';
import userEvent from '@testing-library/user-event';
import { act } from 'react';
import GlobalSearch from '../Search/GlobalSearch';

// Mock AlbumArt component to avoid image loading issues
vi.mock('../../album/AlbumArt', () => ({
  default: function MockAlbumArt({ albumId, size }: any) {
    return (
      <div data-testid={`album-art-${albumId}`} style={{ width: size, height: size }}>
        Album {albumId}
      </div>
    );
  },
}));

// API responses default to a realistic Track.to_dict() payload shape
// (artists[] — the backend never emits a singular `artist` for real rows).
const mockApiResponses: Record<string, unknown> = {};
vi.mock('@/utils/apiRequest', () => ({
  get: vi.fn((url: string) => {
    for (const prefix of Object.keys(mockApiResponses)) {
      if (url.includes(prefix)) return Promise.resolve(mockApiResponses[prefix]);
    }
    return Promise.resolve({});
  }),
}));

function mockSearchResponses(responses: Record<string, unknown>) {
  Object.keys(mockApiResponses).forEach((k) => delete mockApiResponses[k]);
  Object.assign(mockApiResponses, responses);
}

describe('GlobalSearch', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(async () => {
    await act(async () => {
      vi.clearAllTimers();
    });
    vi.useRealTimers();
  });

  describe('Rendering', () => {
    it('should render search input field', () => {
      act(() => {
        render(<GlobalSearch />);
      });

      const input = screen.getByPlaceholderText(/search/i);
      expect(input).toBeInTheDocument();
    });

    it('should have input type text', () => {
      act(() => {
        render(<GlobalSearch />);
      });

      const input = screen.getByPlaceholderText(/search/i) as HTMLInputElement;
      expect(input.type).toBe('text');
    });

    it('should render without crashing', () => {
      let container: any;
      act(() => {
        const result = render(<GlobalSearch />);
        container = result.container;
      });
      expect(container).toBeInTheDocument();
    });
  });

  describe('Input Interaction', () => {
    it('should update input value on type', async () => {
      const user = userEvent.setup();
      await act(async () => {
        render(<GlobalSearch />);
      });

      const input = screen.getByPlaceholderText(/search/i) as HTMLInputElement;

      await act(async () => {
        await user.type(input, 'Queen');
      });

      expect(input.value).toBe('Queen');
    });

    it('should handle text input with special characters', async () => {
      const user = userEvent.setup();
      await act(async () => {
        render(<GlobalSearch />);
      });

      const input = screen.getByPlaceholderText(/search/i) as HTMLInputElement;

      await act(async () => {
        await user.type(input, 'Test & Special');
      });

      expect(input.value).toContain('Test');
      expect(input.value).toContain('Special');
    });

    it('should clear input value', async () => {
      const user = userEvent.setup();
      await act(async () => {
        render(<GlobalSearch />);
      });

      const input = screen.getByPlaceholderText(/search/i) as HTMLInputElement;

      await act(async () => {
        await user.type(input, 'test');
      });

      expect(input.value).toBe('test');

      await act(async () => {
        await user.clear(input);
      });

      expect(input.value).toBe('');
    });
  });

  describe('Accessibility', () => {
    it('should have proper input attributes', () => {
      act(() => {
        render(<GlobalSearch />);
      });

      const input = screen.getByPlaceholderText(/search/i);
      expect(input).toHaveAttribute('type', 'text');
    });

    it('should support keyboard navigation', async () => {
      await act(async () => {
        render(<GlobalSearch />);
      });

      const input = screen.getByPlaceholderText(/search/i);

      // Input should be focusable
      await act(async () => {
        input.focus();
      });

      expect(document.activeElement).toBe(input);
    });
  });

  describe('Edge Cases', () => {
    it('should handle long input text', async () => {
      const user = userEvent.setup();
      await act(async () => {
        render(<GlobalSearch />);
      });

      const input = screen.getByPlaceholderText(/search/i) as HTMLInputElement;
      const longText = 'A'.repeat(200);

      await act(async () => {
        await user.type(input, longText);
      });

      expect(input.value.length).toBe(200);
    });

    it('should handle rapid typing', async () => {
      const user = userEvent.setup();
      await act(async () => {
        render(<GlobalSearch />);
      });

      const input = screen.getByPlaceholderText(/search/i) as HTMLInputElement;

      await act(async () => {
        await user.type(input, 'Queens');
      });

      expect(input.value).toBe('Queens');
    });

    it('should handle unicode input', async () => {
      const user = userEvent.setup();
      await act(async () => {
        render(<GlobalSearch />);
      });

      const input = screen.getByPlaceholderText(/search/i) as HTMLInputElement;

      await act(async () => {
        await user.type(input, '音楽');
      });

      expect(input.value).toBe('音楽');
    });
  });

  describe('Component Lifecycle', () => {
    it('should mount and unmount without errors', () => {
      let unmount: any;
      act(() => {
        const result = render(<GlobalSearch />);
        unmount = result.unmount;
      });

      expect(screen.getByPlaceholderText(/search/i)).toBeInTheDocument();

      act(() => {
        unmount();
      });

      // Component should be removed
      expect(screen.queryByPlaceholderText(/search/i)).not.toBeInTheDocument();
    });

    it('should handle remounting', () => {
      let unmount: any;
      act(() => {
        const result = render(<GlobalSearch />);
        unmount = result.unmount;
      });
      expect(screen.getByPlaceholderText(/search/i)).toBeInTheDocument();

      unmount();

      // Remount
      act(() => {
        render(<GlobalSearch />);
      });
      expect(screen.getByPlaceholderText(/search/i)).toBeInTheDocument();
    });
  });

  // #5516: the search hook read a singular `artist` field the backend never
  // sends for real rows (Track.to_dict emits artists[]), so every track
  // subtitle rendered "undefined • Album".
  describe('Track results use the real payload shape (#5516)', () => {
    async function searchFor(query: string) {
      const user = userEvent.setup();
      await act(async () => {
        render(<GlobalSearch />);
      });
      await user.type(screen.getByPlaceholderText(/search/i), query);
      // The 300ms debounce plus the (mocked) fetch settle before findByText's
      // polling window ends.
    }

    it('renders the artist name from artists[] in the subtitle', async () => {
      mockSearchResponses({
        'library/tracks': {
          tracks: [
            {
              id: 1,
              title: 'One More Time',
              artists: ['Daft Punk'],
              album: 'Discovery',
              album_id: 7,
            },
          ],
        },
        'library/albums': { albums: [] },
        'library/artists': { artists: [] },
      });

      await searchFor('one more');
      expect(await screen.findByText('Daft Punk • Discovery')).toBeInTheDocument();
    });

    it('falls back gracefully when artists[] and album are absent', async () => {
      mockSearchResponses({
        'library/tracks': { tracks: [{ id: 2, title: 'Untitled' }] },
        'library/albums': { albums: [] },
        'library/artists': { artists: [] },
      });

      await searchFor('untitled');
      expect(await screen.findByText('Untitled')).toBeInTheDocument();
      expect(screen.queryByText(/undefined/)).not.toBeInTheDocument();
    });
  });
});
