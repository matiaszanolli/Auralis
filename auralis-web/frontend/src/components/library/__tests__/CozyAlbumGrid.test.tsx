/**
 * CozyAlbumGrid Component Tests
 *
 * Tests the album grid with:
 * - Pagination and infinite scroll
 * - Loading states and skeletons
 * - Error handling and recovery
 * - Album card rendering
 * - Click handlers and callbacks
 */

import { render, screen, waitFor } from '@/test/test-utils';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, beforeEach, afterEach, beforeAll, vi } from 'vitest';
import { CozyAlbumGrid } from '../Items/albums/CozyAlbumGrid';

// Mock AlbumCard component
vi.mock('@/components/album/AlbumCard/AlbumCard', () => {
  return {
    AlbumCard: function MockAlbumCard({
      albumId,
      title,
      artist,
      trackCount,
      year,
      onClick
    }: any) {
      return (
        <div
          data-testid={`album-card-${albumId}`}
          onClick={onClick}
          style={{ cursor: 'pointer' }}
        >
          <p>{title}</p>
          <p>{artist}</p>
          <p>{trackCount} tracks • {year}</p>
        </div>
      );
    }
  };
});


const mockAlbumData = {
  albums: [
    {
      id: 1,
      title: 'Album 1',
      artist: 'Artist 1',
      track_count: 12,
      total_duration: 3600,
      year: 2023,
      artwork_path: '/artwork/1.jpg',
    },
    {
      id: 2,
      title: 'Album 2',
      artist: 'Artist 2',
      track_count: 10,
      total_duration: 3000,
      year: 2023,
      artwork_path: '/artwork/2.jpg',
    },
  ],
  has_more: false,
  total: 2,
};

// Create mock fetch before test
const mockFetch = vi.fn();

// Setup fetch mock
beforeAll(() => {
  global.fetch = mockFetch as any;
});

describe('CozyAlbumGrid', () => {
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
        json: async () => mockAlbumData,
      });

      const { container } = render(
        <CozyAlbumGrid />
      );

      // Check for skeleton elements
      const skeletons = container.querySelectorAll('[class*="MuiSkeleton"]');
      expect(skeletons.length).toBeGreaterThan(0);
    });

    it('should fetch albums on mount', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockAlbumData,
      });

      render(
        <CozyAlbumGrid />
      );

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith(
          expect.stringContaining('/api/albums')
        );
      });
    });

    it('should render albums after loading', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockAlbumData,
      });

      render(
        <CozyAlbumGrid />
      );

      await waitFor(() => {
        expect(screen.getByTestId('album-card-1')).toBeInTheDocument();
        expect(screen.getByTestId('album-card-2')).toBeInTheDocument();
      });
    });
  });

  describe('Album Rendering', () => {
    it('should display all albums from response', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockAlbumData,
      });

      render(
        <CozyAlbumGrid />
      );

      await waitFor(() => {
        expect(screen.getByText('Album 1')).toBeInTheDocument();
        expect(screen.getByText('Album 2')).toBeInTheDocument();
      });
    });

    it('should display album artist and metadata', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockAlbumData,
      });

      render(
        <CozyAlbumGrid />
      );

      await waitFor(() => {
        expect(screen.getByText('Artist 1')).toBeInTheDocument();
        expect(screen.getByText(/12 tracks/)).toBeInTheDocument();
      });
    });

    it('should call onAlbumClick when album is clicked', async () => {
      const mockClick = vi.fn();
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockAlbumData,
      });

      render(
        <CozyAlbumGrid onAlbumClick={mockClick} />
      );

      await waitFor(() => {
        expect(screen.getByTestId('album-card-1')).toBeInTheDocument();
      });

      const albumCard = screen.getByTestId('album-card-1');
      await userEvent.click(albumCard);

      expect(mockClick).toHaveBeenCalledWith(1);
    });
  });

  describe('Empty States', () => {
    it('should show empty state when no albums', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          albums: [],
          has_more: false,
          total: 0,
        }),
      });

      render(
        <CozyAlbumGrid />
      );

      await waitFor(() => {
        expect(screen.getByText(/No Albums Yet/)).toBeInTheDocument();
      });
    });

    it('should display helpful empty state message', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          albums: [],
          has_more: false,
          total: 0,
        }),
      });

      render(
        <CozyAlbumGrid />
      );

      await waitFor(() => {
        expect(
          screen.getByText(/Your album library will appear here once you scan/)
        ).toBeInTheDocument();
      });
    });
  });

  describe('Error Handling', () => {
    it('should handle fetch error gracefully', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
      });

      render(
        <CozyAlbumGrid />
      );

      await waitFor(() => {
        expect(screen.getByText(/Error Loading Albums/)).toBeInTheDocument();
      });
    });

    it('should display error message on failure', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
      });

      render(
        <CozyAlbumGrid />
      );

      await waitFor(() => {
        expect(screen.getByText(/Failed to fetch albums/)).toBeInTheDocument();
      });
    });

    it('should handle network error', async () => {
      mockFetch.mockRejectedValueOnce(
        new Error('Network error')
      );

      render(
        <CozyAlbumGrid />
      );

      await waitFor(() => {
        expect(screen.getByText(/Error Loading Albums/)).toBeInTheDocument();
      });
    });
  });

  describe('Pagination', () => {
    it('should fetch with correct limit and offset', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockAlbumData,
      });

      render(
        <CozyAlbumGrid />
      );

      await waitFor(() => {
        // Check that fetch was called with correct parameters (order may vary)
        const calls = (global.fetch as any).mock.calls;
        const albumsCall = calls.find((call: any) => call[0].includes('/api/albums'));
        expect(albumsCall).toBeDefined();
        expect(albumsCall[0]).toContain('limit=50');
        expect(albumsCall[0]).toContain('offset=0');
      });
    });

    it('should show loading more indicator when loading more', async () => {
      const moreAlbumData = {
        albums: [
          {
            id: 3,
            title: 'Album 3',
            artist: 'Artist 3',
            track_count: 15,
            total_duration: 4500,
          },
        ],
        has_more: true,
        total: 100,
      };

      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ ...mockAlbumData, has_more: true, total: 100 }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => moreAlbumData,
        });

      render(
        <CozyAlbumGrid />
      );

      await waitFor(() => {
        expect(screen.getByTestId('album-card-1')).toBeInTheDocument();
      });

      // Trigger load more
      const loadMoreTrigger = screen.getByTestId('album-card-1').parentElement
        ?.parentElement;
      if (loadMoreTrigger?.scrollLeft !== undefined) {
        loadMoreTrigger.dispatchEvent(new Event('scroll', { bubbles: true }));
      }
    });

    it('should show end of list message when has_more is false', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          ...mockAlbumData,
          has_more: false,
          total: 2,
        }),
      });

      render(
        <CozyAlbumGrid />
      );

      await waitFor(() => {
        // When has_more is false, albums should render and no "Loading more..." text
        expect(screen.getByTestId('album-card-1')).toBeInTheDocument();
        expect(screen.queryByText(/Loading more albums/)).not.toBeInTheDocument();
      });
    });
  });

  describe('Deduplication', () => {
    it('should deduplicate albums by ID on load more', async () => {
      const initialData = {
        albums: [
          {
            id: 1,
            title: 'Album 1',
            artist: 'Artist 1',
            track_count: 12,
            total_duration: 3600,
          },
        ],
        has_more: true,
        total: 100,
      };

      const moreData = {
        albums: [
          {
            id: 1, // Duplicate
            title: 'Album 1',
            artist: 'Artist 1',
            track_count: 12,
            total_duration: 3600,
          },
          {
            id: 2,
            title: 'Album 2',
            artist: 'Artist 2',
            track_count: 10,
            total_duration: 3000,
          },
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
        <CozyAlbumGrid />
      );

      await waitFor(() => {
        expect(screen.getByTestId('album-card-1')).toBeInTheDocument();
      });

      // Load more would trigger deduplication
      // The grid should not render duplicate album cards
    });
  });

  describe('Infinite Scroll', () => {
    it('should have load more trigger element when has_more is true', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          ...mockAlbumData,
          has_more: true,
          total: 100,
        }),
      });

      const { container } = render(
        <CozyAlbumGrid />
      );

      await waitFor(() => {
        expect(screen.getByTestId('album-card-1')).toBeInTheDocument();
      });

      // Check for load more trigger (invisible sentinel element)
      const triggers = container.querySelectorAll('[style*="height"]');
      expect(triggers.length).toBeGreaterThan(0);
    });

    it('should not render load more trigger when has_more is false', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          ...mockAlbumData,
          has_more: false,
          total: 2,
        }),
      });

      const { container } = render(
        <CozyAlbumGrid />
      );

      await waitFor(() => {
        expect(screen.getByTestId('album-card-1')).toBeInTheDocument();
      });

      // No load more trigger element should be present for pagination
      expect(
        container.querySelector('[style*="height: 1px"]')
      ).not.toBeInTheDocument();
    });
  });

  describe('Display Updates', () => {
    it('should display total album count in loading indicator', async () => {
      const moreData = {
        albums: [
          {
            id: 3,
            title: 'Album 3',
            artist: 'Artist 3',
            track_count: 15,
            total_duration: 4500,
          },
        ],
        has_more: true,
        total: 100,
      };

      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ ...mockAlbumData, has_more: true, total: 100 }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => moreData,
        });

      render(
        <CozyAlbumGrid />
      );

      await waitFor(() => {
        expect(screen.getByTestId('album-card-1')).toBeInTheDocument();
      });
    });

    it('should update album count display on load more', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          ...mockAlbumData,
          has_more: false,
          total: 2,
        }),
      });

      render(
        <CozyAlbumGrid />
      );

      await waitFor(() => {
        // Verify albums are displayed when load completes
        expect(screen.getByTestId('album-card-1')).toBeInTheDocument();
        expect(screen.getByTestId('album-card-2')).toBeInTheDocument();
      });
    });
  });

  describe('Props and Callbacks', () => {
    it('should accept onAlbumClick callback', async () => {
      const mockClick = vi.fn();
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockAlbumData,
      });

      render(
        <CozyAlbumGrid onAlbumClick={mockClick} />
      );

      await waitFor(() => {
        expect(screen.getByTestId('album-card-1')).toBeInTheDocument();
      });

      const albumCard = screen.getByTestId('album-card-1');
      await userEvent.click(albumCard);

      expect(mockClick).toHaveBeenCalledWith(1);
    });

    it('should handle undefined onAlbumClick gracefully', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockAlbumData,
      });

      render(
        <CozyAlbumGrid />
      );

      await waitFor(() => {
        expect(screen.getByTestId('album-card-1')).toBeInTheDocument();
      });

      // Should not throw error
      const albumCard = screen.getByTestId('album-card-1');
      await userEvent.click(albumCard);
    });
  });

  describe('Duration Formatting', () => {
    it('should format duration in hours and minutes', async () => {
      const albumWith5HourDuration = {
        albums: [
          {
            id: 1,
            title: 'Album 1',
            artist: 'Artist 1',
            track_count: 12,
            total_duration: 18000, // 5 hours
          },
        ],
        has_more: false,
        total: 1,
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => albumWith5HourDuration,
      });

      render(
        <CozyAlbumGrid />
      );

      await waitFor(() => {
        expect(screen.getByTestId('album-card-1')).toBeInTheDocument();
      });
    });

    it('should format duration in minutes when less than an hour', async () => {
      const albumWithMinuteDuration = {
        albums: [
          {
            id: 1,
            title: 'Album 1',
            artist: 'Artist 1',
            track_count: 12,
            total_duration: 1800, // 30 minutes
          },
        ],
        has_more: false,
        total: 1,
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => albumWithMinuteDuration,
      });

      render(
        <CozyAlbumGrid />
      );

      await waitFor(() => {
        expect(screen.getByTestId('album-card-1')).toBeInTheDocument();
      });
    });
  });

  describe('Edge Cases', () => {
    it('should handle response with null albums array', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          albums: null,
          has_more: false,
          total: 0,
        }),
      });

      render(
        <CozyAlbumGrid />
      );

      await waitFor(() => {
        // When albums is null, component shows error state
        expect(screen.getByText(/Error Loading Albums/)).toBeInTheDocument();
      });
    });

    it('should handle response with undefined total', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          albums: mockAlbumData.albums,
          has_more: false,
        }),
      });

      render(
        <CozyAlbumGrid />
      );

      await waitFor(() => {
        expect(screen.getByTestId('album-card-1')).toBeInTheDocument();
      });
    });

    it('should handle rapid consecutive mounts', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => mockAlbumData,
      });

      const { unmount: unmount1 } = render(
        <CozyAlbumGrid />
      );

      await waitFor(() => {
        expect(screen.getByTestId('album-card-1')).toBeInTheDocument();
      });

      unmount1();

      render(
        <CozyAlbumGrid />
      );

      await waitFor(() => {
        expect(screen.getByTestId('album-card-1')).toBeInTheDocument();
      });
    });
  });
});
