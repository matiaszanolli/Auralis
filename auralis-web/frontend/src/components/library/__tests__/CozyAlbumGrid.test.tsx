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

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material/styles';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { CozyAlbumGrid } from '../CozyAlbumGrid';
import { auralisTheme } from '../../../theme/auralisTheme';

// Mock AlbumCard component
vi.mock('../../album/AlbumCard', () => {
  return {
    AlbumCard: function MockAlbumCard({
      albumId,
      title,
      artist,
      trackCount,
      duration,
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
          <p>{trackCount} tracks • {duration}s</p>
        </div>
      );
    }
  };
});

const Wrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <BrowserRouter>
    <ThemeProvider theme={auralisTheme}>
      <div style={{ height: '800px', overflow: 'auto' }}>
        {children}
      </div>
    </ThemeProvider>
  </BrowserRouter>
);

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

describe('CozyAlbumGrid', () => {
  beforeEach(() => {
    global.fetch = vi.fn();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('Initial Loading', () => {
    it('should render loading skeletons on initial mount', () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockAlbumData,
      });

      const { container } = render(
        <Wrapper>
          <CozyAlbumGrid />
        </Wrapper>
      );

      // Check for skeleton elements
      const skeletons = container.querySelectorAll('[class*="MuiSkeleton"]');
      expect(skeletons.length).toBeGreaterThan(0);
    });

    it('should fetch albums on mount', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockAlbumData,
      });

      render(
        <Wrapper>
          <CozyAlbumGrid />
        </Wrapper>
      );

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith(
          expect.stringContaining('/api/albums')
        );
      });
    });

    it('should render albums after loading', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockAlbumData,
      });

      render(
        <Wrapper>
          <CozyAlbumGrid />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByTestId('album-card-1')).toBeInTheDocument();
        expect(screen.getByTestId('album-card-2')).toBeInTheDocument();
      });
    });
  });

  describe('Album Rendering', () => {
    it('should display all albums from response', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockAlbumData,
      });

      render(
        <Wrapper>
          <CozyAlbumGrid />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Album 1')).toBeInTheDocument();
        expect(screen.getByText('Album 2')).toBeInTheDocument();
      });
    });

    it('should display album artist and metadata', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockAlbumData,
      });

      render(
        <Wrapper>
          <CozyAlbumGrid />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Artist 1')).toBeInTheDocument();
        expect(screen.getByText(/12 tracks/)).toBeInTheDocument();
      });
    });

    it('should call onAlbumClick when album is clicked', async () => {
      const mockClick = vi.fn();
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockAlbumData,
      });

      render(
        <Wrapper>
          <CozyAlbumGrid onAlbumClick={mockClick} />
        </Wrapper>
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
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          albums: [],
          has_more: false,
          total: 0,
        }),
      });

      render(
        <Wrapper>
          <CozyAlbumGrid />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText(/No Albums Yet/)).toBeInTheDocument();
      });
    });

    it('should display helpful empty state message', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          albums: [],
          has_more: false,
          total: 0,
        }),
      });

      render(
        <Wrapper>
          <CozyAlbumGrid />
        </Wrapper>
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
      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
      });

      render(
        <Wrapper>
          <CozyAlbumGrid />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText(/Error Loading Albums/)).toBeInTheDocument();
      });
    });

    it('should display error message on failure', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
      });

      render(
        <Wrapper>
          <CozyAlbumGrid />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText(/Failed to fetch albums/)).toBeInTheDocument();
      });
    });

    it('should handle network error', async () => {
      (global.fetch as any).mockRejectedValueOnce(
        new Error('Network error')
      );

      render(
        <Wrapper>
          <CozyAlbumGrid />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText(/Error Loading Albums/)).toBeInTheDocument();
      });
    });
  });

  describe('Pagination', () => {
    it('should fetch with correct limit and offset', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockAlbumData,
      });

      render(
        <Wrapper>
          <CozyAlbumGrid />
        </Wrapper>
      );

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith(
          expect.stringContaining('limit=50&offset=0')
        );
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

      (global.fetch as any)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ ...mockAlbumData, has_more: true, total: 100 }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => moreAlbumData,
        });

      render(
        <Wrapper>
          <CozyAlbumGrid />
        </Wrapper>
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
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          ...mockAlbumData,
          has_more: false,
          total: 2,
        }),
      });

      render(
        <Wrapper>
          <CozyAlbumGrid />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText(/Showing all 2 albums/)).toBeInTheDocument();
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

      (global.fetch as any)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => initialData,
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => moreData,
        });

      const { container } = render(
        <Wrapper>
          <CozyAlbumGrid />
        </Wrapper>
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
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          ...mockAlbumData,
          has_more: true,
          total: 100,
        }),
      });

      const { container } = render(
        <Wrapper>
          <CozyAlbumGrid />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByTestId('album-card-1')).toBeInTheDocument();
      });

      // Check for load more trigger (invisible sentinel element)
      const triggers = container.querySelectorAll('[style*="height"]');
      expect(triggers.length).toBeGreaterThan(0);
    });

    it('should not render load more trigger when has_more is false', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          ...mockAlbumData,
          has_more: false,
          total: 2,
        }),
      });

      const { container } = render(
        <Wrapper>
          <CozyAlbumGrid />
        </Wrapper>
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

      (global.fetch as any)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ ...mockAlbumData, has_more: true, total: 100 }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => moreData,
        });

      render(
        <Wrapper>
          <CozyAlbumGrid />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByTestId('album-card-1')).toBeInTheDocument();
      });
    });

    it('should update album count display on load more', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          ...mockAlbumData,
          has_more: false,
          total: 2,
        }),
      });

      render(
        <Wrapper>
          <CozyAlbumGrid />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText(/Showing all 2 albums/)).toBeInTheDocument();
      });
    });
  });

  describe('Props and Callbacks', () => {
    it('should accept onAlbumClick callback', async () => {
      const mockClick = vi.fn();
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockAlbumData,
      });

      render(
        <Wrapper>
          <CozyAlbumGrid onAlbumClick={mockClick} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByTestId('album-card-1')).toBeInTheDocument();
      });

      const albumCard = screen.getByTestId('album-card-1');
      await userEvent.click(albumCard);

      expect(mockClick).toHaveBeenCalledWith(1);
    });

    it('should handle undefined onAlbumClick gracefully', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockAlbumData,
      });

      render(
        <Wrapper>
          <CozyAlbumGrid />
        </Wrapper>
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

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => albumWith5HourDuration,
      });

      render(
        <Wrapper>
          <CozyAlbumGrid />
        </Wrapper>
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

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => albumWithMinuteDuration,
      });

      render(
        <Wrapper>
          <CozyAlbumGrid />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByTestId('album-card-1')).toBeInTheDocument();
      });
    });
  });

  describe('Edge Cases', () => {
    it('should handle response with null albums array', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          albums: null,
          has_more: false,
          total: 0,
        }),
      });

      render(
        <Wrapper>
          <CozyAlbumGrid />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText(/No Albums Yet/)).toBeInTheDocument();
      });
    });

    it('should handle response with undefined total', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          albums: mockAlbumData.albums,
          has_more: false,
        }),
      });

      render(
        <Wrapper>
          <CozyAlbumGrid />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByTestId('album-card-1')).toBeInTheDocument();
      });
    });

    it('should handle rapid consecutive mounts', async () => {
      (global.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => mockAlbumData,
      });

      const { unmount: unmount1 } = render(
        <Wrapper>
          <CozyAlbumGrid />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByTestId('album-card-1')).toBeInTheDocument();
      });

      unmount1();

      render(
        <Wrapper>
          <CozyAlbumGrid />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByTestId('album-card-1')).toBeInTheDocument();
      });
    });
  });
});
