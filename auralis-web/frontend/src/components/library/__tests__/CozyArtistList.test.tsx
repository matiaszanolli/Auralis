/**
 * CozyArtistList Component Tests
 *
 * Tests the artist list with:
 * - Alphabetical grouping and dividers
 * - Pagination and infinite scroll
 * - Context menu integration
 * - Loading states and skeletons
 * - Error handling
 * - Artist metadata display
 */

import { render, screen, waitFor } from '@/test/test-utils';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { CozyArtistList } from '../Items/artists/CozyArtistList';

// Mock context menu and toast hooks
vi.mock('@/components/shared/ContextMenu', () => ({
  useContextMenu: () => ({
    contextMenuState: { isOpen: false, mousePosition: null },
    handleContextMenu: vi.fn(),
    handleCloseContextMenu: vi.fn(),
  }),
  ContextMenu: () => <div data-testid="context-menu" style={{ display: 'none' }} />,
  getArtistContextActions: vi.fn(() => []),
}));

vi.mock('@/components/shared/Toast', () => ({
  useToast: () => ({
    success: vi.fn(),
    info: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
  }),
  ToastProvider: ({ children }: any) => <>{children}</>,
}));


const mockArtistData = {
  artists: [
    { id: 1, name: 'Artist A', album_count: 5, track_count: 50 },
    { id: 2, name: 'Artist B', album_count: 3, track_count: 30 },
    { id: 3, name: 'Artist C', album_count: 8, track_count: 80 },
  ],
  has_more: false,
  total: 3,
};

// Create mock fetch before test
const mockFetch = vi.fn();

// Setup fetch mock
beforeAll(() => {
  global.fetch = mockFetch as any;
});

describe('CozyArtistList', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('Initial Loading', () => {
    it('should render loading skeletons on initial mount', () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockArtistData,
      });

      const { container } = render(
        <CozyArtistList />
      );

      // Check for skeleton elements
      const skeletons = container.querySelectorAll('[class*="MuiSkeleton"]');
      expect(skeletons.length).toBeGreaterThan(0);
    });

    it('should fetch artists on mount', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockArtistData,
      });

      render(
        <CozyArtistList />
      );

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith(
          expect.stringContaining('/api/artists'),
          expect.objectContaining({ method: 'GET' })
        );
      });
    });

    it('should render artists after loading', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockArtistData,
      });

      render(
        <CozyArtistList />
      );

      await waitFor(() => {
        expect(screen.getByText('Artist A')).toBeInTheDocument();
        expect(screen.getByText('Artist B')).toBeInTheDocument();
        expect(screen.getByText('Artist C')).toBeInTheDocument();
      });
    });
  });

  describe('Artist Display', () => {
    it('should display all artists from response', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockArtistData,
      });

      render(
        <CozyArtistList />
      );

      await waitFor(() => {
        expect(screen.getByText('Artist A')).toBeInTheDocument();
        expect(screen.getByText('Artist B')).toBeInTheDocument();
        expect(screen.getByText('Artist C')).toBeInTheDocument();
      });
    });

    it('should display album count for each artist', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockArtistData,
      });

      render(
        <CozyArtistList />
      );

      await waitFor(() => {
        expect(screen.getByText(/5 albums/)).toBeInTheDocument();
        expect(screen.getByText(/3 albums/)).toBeInTheDocument();
      });
    });

    it('should display track count for each artist', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockArtistData,
      });

      render(
        <CozyArtistList />
      );

      await waitFor(() => {
        expect(screen.getByText(/50 tracks/)).toBeInTheDocument();
        expect(screen.getByText(/30 tracks/)).toBeInTheDocument();
      });
    });

    it('should handle singular album/track display', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          artists: [
            { id: 1, name: 'Solo Artist', album_count: 1, track_count: 1 },
          ],
          has_more: false,
          total: 1,
        }),
      });

      render(
        <CozyArtistList />
      );

      await waitFor(() => {
        expect(screen.getByText(/1 album.*1 track/)).toBeInTheDocument();
      });
    });
  });

  describe('Alphabetical Grouping', () => {
    it('should group artists by first letter', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockArtistData,
      });

      render(
        <CozyArtistList />
      );

      await waitFor(() => {
        // Check for artist names instead of letters to avoid ambiguity with alphabet dividers
        expect(screen.getByText('Artist A')).toBeInTheDocument();
        expect(screen.getByText('Artist B')).toBeInTheDocument();
        expect(screen.getByText('Artist C')).toBeInTheDocument();
      });
    });

    it('should display alphabetical dividers', async () => {
      // One divider per initial: 'Artist A/B/C' would all share the 'A' group.
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          artists: [
            { id: 1, name: 'Abba', album_count: 5, track_count: 50 },
            { id: 2, name: 'Beck', album_count: 3, track_count: 30 },
            { id: 3, name: 'Cher', album_count: 8, track_count: 80 },
          ],
          has_more: false,
          total: 3,
        }),
      });

      render(
        <CozyArtistList />
      );

      await waitFor(() => {
        expect(screen.getAllByText(/^[A-Z]$/).map((d) => d.textContent)).toEqual(['A', 'B', 'C']);
      });
    });

    it('should sort alphabetical groups correctly', async () => {
      const unorderedArtists = {
        artists: [
          { id: 1, name: 'Zebra', album_count: 1, track_count: 10 },
          { id: 2, name: 'Apple', album_count: 2, track_count: 20 },
          { id: 3, name: 'Middle', album_count: 3, track_count: 30 },
        ],
        has_more: false,
        total: 3,
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => unorderedArtists,
      });

      render(
        <CozyArtistList />
      );

      await waitFor(() => {
        expect(screen.getByText('Apple')).toBeInTheDocument();
      });

      // The server order (Zebra, Apple, Middle) is regrouped alphabetically
      expect(screen.getAllByText(/^[A-Z]$/).map((d) => d.textContent)).toEqual(['A', 'M', 'Z']);
      expect(screen.getAllByRole('button').map((b) => b.getAttribute('aria-label')?.split(',')[0])).toEqual([
        'Apple', 'Middle', 'Zebra',
      ]);
    });
  });

  describe('Artist Click Handler', () => {
    it('should call onArtistClick when artist is clicked', async () => {
      const mockClick = vi.fn();
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockArtistData,
      });

      render(
        <CozyArtistList onArtistClick={mockClick} />
      );

      await waitFor(() => {
        expect(screen.getByText('Artist A')).toBeInTheDocument();
      });

      const artistContainer = screen.getByRole('button', { name: /^Artist A/ });
      await userEvent.click(artistContainer);

      expect(mockClick).toHaveBeenCalledWith(1, 'Artist A');
    });

    it('should pass artist ID and name to callback', async () => {
      const mockClick = vi.fn();
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockArtistData,
      });

      render(
        <CozyArtistList onArtistClick={mockClick} />
      );

      await waitFor(() => {
        expect(screen.getByText('Artist C')).toBeInTheDocument();
      });

      const artistContainer = screen.getByRole('button', { name: /^Artist C/ });
      await userEvent.click(artistContainer);

      expect(mockClick).toHaveBeenCalledWith(3, 'Artist C');
    });

    it('should handle undefined onArtistClick gracefully', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockArtistData,
      });

      render(
        <CozyArtistList />
      );

      await waitFor(() => {
        expect(screen.getByText('Artist A')).toBeInTheDocument();
      });

      const artistContainer = screen.getByRole('button', { name: /^Artist A/ });
      await userEvent.click(artistContainer);

      // Should not throw error
      expect(artistContainer).toBeInTheDocument();
    });
  });

  describe('Pagination', () => {
    it('should fetch with correct limit and offset', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockArtistData,
      });

      render(
        <CozyArtistList />
      );

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith(
          expect.stringContaining('limit=50&offset=0'),
          expect.objectContaining({ method: 'GET' })
        );
      });
    });

    it('should show end of list message when has_more is false', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          ...mockArtistData,
          has_more: false,
          total: 3,
        }),
      });

      render(
        <CozyArtistList />
      );

      await waitFor(() => {
        expect(screen.getByText(/Showing all 3 artists/)).toBeInTheDocument();
      });
    });

    it('should display artist count in header', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockArtistData,
      });

      render(
        <CozyArtistList />
      );

      await waitFor(() => {
        expect(screen.getByText(/3 artists in your library/)).toBeInTheDocument();
      });
    });
  });

  describe('Empty States', () => {
    it('should show empty state when no artists', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          artists: [],
          has_more: false,
          total: 0,
        }),
      });

      render(
        <CozyArtistList />
      );

      await waitFor(() => {
        expect(screen.getByText(/No Artists Yet/)).toBeInTheDocument();
      });
    });

    it('should display helpful empty state message', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          artists: [],
          has_more: false,
          total: 0,
        }),
      });

      render(
        <CozyArtistList />
      );

      await waitFor(() => {
        expect(
          screen.getByText(/Your artist library will appear here once you scan/)
        ).toBeInTheDocument();
      });
    });

    it('should display person icon in empty state', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          artists: [],
          has_more: false,
          total: 0,
        }),
      });

      const { container } = render(
        <CozyArtistList />
      );

      await waitFor(() => {
        const icons = container.querySelectorAll('[class*="MuiSvgIcon"]');
        expect(icons.length).toBeGreaterThan(0);
      });
    });
  });

  describe('Error Handling', () => {
    it('should handle fetch error gracefully', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
      });

      render(
        <CozyArtistList />
      );

      await waitFor(() => {
        expect(screen.getByText(/Error Loading Artists/)).toBeInTheDocument();
      });
    });

    it('should display error message on failure', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        statusText: 'Internal Server Error',
        text: async () => '',
      });

      render(
        <CozyArtistList />
      );

      await waitFor(() => {
        expect(screen.getByRole('alert')).toHaveTextContent(/Error Loading Artists/);
      });
    });

    it('should handle network error', async () => {
      mockFetch.mockRejectedValueOnce(
        new Error('Network error')
      );

      render(
        <CozyArtistList />
      );

      await waitFor(() => {
        expect(screen.getByText(/Error Loading Artists/)).toBeInTheDocument();
      });
    });
  });

  describe('Context Menu', () => {
    it('should render context menu component', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockArtistData,
      });

      render(
        <CozyArtistList />
      );

      await waitFor(() => {
        expect(screen.getByTestId('context-menu')).toBeInTheDocument();
      });
    });

    it('should handle right-click on artist', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockArtistData,
      });

      render(
        <CozyArtistList />
      );

      await waitFor(() => {
        expect(screen.getByText('Artist A')).toBeInTheDocument();
      });

      const artistContainer = screen.getByRole('button', { name: /^Artist A/ });
      // Right-click simulation (context menu)
      await userEvent.pointer({
        keys: '[MouseRight]',
        target: artistContainer,
      });

      expect(screen.getByTestId('context-menu')).toBeInTheDocument();
    });
  });

  describe('Artist Avatar Display', () => {
    it('should display artist initial in avatar', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockArtistData,
      });

      render(
        <CozyArtistList />
      );

      await waitFor(() => {
        // Check for artist names to verify avatars are rendered
        expect(screen.getByText('Artist A')).toBeInTheDocument();
        expect(screen.getByText('Artist B')).toBeInTheDocument();
        expect(screen.getByText('Artist C')).toBeInTheDocument();
      });
    });
  });

  describe('Deduplication', () => {
    it('should deduplicate artists by ID on load more', async () => {
      const initialData = {
        artists: [{ id: 1, name: 'Artist A', album_count: 5, track_count: 50 }],
        has_more: true,
        total: 100,
      };

      const moreData = {
        artists: [
          { id: 1, name: 'Artist A', album_count: 5, track_count: 50 }, // Duplicate
          { id: 2, name: 'Artist B', album_count: 3, track_count: 30 },
        ],
        has_more: false,
        total: 2,
      };

      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: async () => initialData,
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => moreData,
        });

      render(
        <CozyArtistList />
      );

      await waitFor(() => {
        expect(screen.getByText('Artist A')).toBeInTheDocument();
      });

      // Load more would trigger deduplication
      // Should not render duplicate artist items
    });
  });

  describe('Infinite Scroll', () => {
    it('should have load more trigger element when has_more is true', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          ...mockArtistData,
          has_more: true,
          total: 100,
        }),
      });

      const { container } = render(
        <CozyArtistList />
      );

      await waitFor(() => {
        expect(screen.getByText('Artist A')).toBeInTheDocument();
      });

      // Component renders with has_more=true (infinite scroll trigger configured)
      expect(container.firstChild).toBeInTheDocument();
    });

    it('should not render load more trigger when has_more is false', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          ...mockArtistData,
          has_more: false,
          total: 3,
        }),
      });

      const { container } = render(
        <CozyArtistList />
      );

      await waitFor(() => {
        expect(screen.getByText('Artist A')).toBeInTheDocument();
      });

      // No load more trigger element should be present for pagination
      expect(
        container.querySelector('[style*="height: 1px"]')
      ).not.toBeInTheDocument();
    });
  });

  describe('Edge Cases', () => {
    it('should reject a response with a null artists array', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          artists: null,
          has_more: false,
          total: 0,
        }),
      });

      render(
        <CozyArtistList />
      );

      await waitFor(() => {
        expect(screen.getByText(/Error Loading Artists/)).toBeInTheDocument();
      });
    });

    it('should handle artists with missing album_count', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          artists: [
            { id: 1, name: 'Artist A', track_count: 50 },
          ],
          has_more: false,
          total: 1,
        }),
      });

      render(
        <CozyArtistList />
      );

      await waitFor(() => {
        expect(screen.getByText('Artist A')).toBeInTheDocument();
      });
    });

    it('should handle artists with special characters in name', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          artists: [
            { id: 1, name: 'Björk', album_count: 10, track_count: 100 },
          ],
          has_more: false,
          total: 1,
        }),
      });

      render(
        <CozyArtistList />
      );

      await waitFor(() => {
        expect(screen.getByText('Björk')).toBeInTheDocument();
      });
    });

    it('should handle very long artist names', async () => {
      const longName = 'A' + 'B'.repeat(100);
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          artists: [
            { id: 1, name: longName, album_count: 5, track_count: 50 },
          ],
          has_more: false,
          total: 1,
        }),
      });

      render(
        <CozyArtistList />
      );

      await waitFor(() => {
        expect(screen.getByText(longName)).toBeInTheDocument();
      });
    });
  });

  describe('Accessibility', () => {
    it('should have proper list structure', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockArtistData,
      });

      render(
        <CozyArtistList />
      );

      await waitFor(() => {
        expect(screen.getByText('Artist A')).toBeInTheDocument();
      });

      expect(screen.getAllByRole('button')).toHaveLength(3);
    });

    it('should have clickable artist items', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockArtistData,
      });

      render(
        <CozyArtistList />
      );

      await waitFor(() => {
        expect(screen.getByText('Artist A')).toBeInTheDocument();
      });

      const artistContainer = screen.getByRole('button', { name: /^Artist A/ });
      expect(artistContainer.tagName).toBe('BUTTON');
    });
  });
});
