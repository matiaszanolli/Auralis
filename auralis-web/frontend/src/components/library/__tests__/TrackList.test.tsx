/**
 * TrackList Component Tests
 * ~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Tests for track list component including:
 * - Track rendering and display
 * - Infinite scroll with Intersection Observer
 * - Selection state management
 * - Click handlers and callbacks
 * - Loading and error states
 * - Empty state
 *
 * @module components/library/__tests__/TrackList.test
 */

import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { vi } from 'vitest';
import TrackList from '@/components/library/TrackList';
import { useTracksQuery } from '@/hooks/library/useLibraryQuery';
import type { Track } from '@/types/domain';

// Mock useTracksQuery hook
vi.mock('@/hooks/library/useLibraryQuery');

// Mock IntersectionObserver
const mockIntersectionObserver = vi.fn();
mockIntersectionObserver.mockReturnValue({
  observe: vi.fn(),
  unobserve: vi.fn(),
  disconnect: vi.fn(),
});
window.IntersectionObserver = mockIntersectionObserver as any;

// Mock data
const mockTrack1: Track = {
  id: 1,
  title: 'First Song',
  artist: 'Artist One',
  album: 'Album One',
  duration: 180,
  filepath: '/path/to/song1.wav',
};

const mockTrack2: Track = {
  id: 2,
  title: 'Second Song',
  artist: 'Artist Two',
  album: 'Album Two',
  duration: 240,
  filepath: '/path/to/song2.wav',
};

const mockTrack3: Track = {
  id: 3,
  title: 'Third Song',
  artist: 'Artist Three',
  album: 'Album Three',
  duration: 200,
  filepath: '/path/to/song3.wav',
};

describe('TrackList', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('rendering', () => {
    it('should render tracks in a list', () => {
      vi.mocked(useTracksQuery).mockReturnValue({
        data: [mockTrack1, mockTrack2],
        isLoading: false,
        error: null,
        total: 2,
        offset: 0,
        hasMore: false,
        fetchMore: vi.fn(),
        refetch: vi.fn(),
        clearError: vi.fn(),
      });

      render(<TrackList />);

      expect(screen.getByText('First Song')).toBeInTheDocument();
      expect(screen.getByText('Second Song')).toBeInTheDocument();
    });

    it('should display track number, title, artist, album, and duration', () => {
      vi.mocked(useTracksQuery).mockReturnValue({
        data: [mockTrack1],
        isLoading: false,
        error: null,
        total: 1,
        offset: 0,
        hasMore: false,
        fetchMore: vi.fn(),
        refetch: vi.fn(),
        clearError: vi.fn(),
      });

      render(<TrackList />);

      expect(screen.getByText('1')).toBeInTheDocument();
      expect(screen.getByText('First Song')).toBeInTheDocument();
      expect(screen.getByText('Artist One')).toBeInTheDocument();
      expect(screen.getByText('Album One')).toBeInTheDocument();
      expect(screen.getByText('3:00')).toBeInTheDocument();
    });

    it('should display separator between artist and album', () => {
      vi.mocked(useTracksQuery).mockReturnValue({
        data: [mockTrack1],
        isLoading: false,
        error: null,
        total: 1,
        offset: 0,
        hasMore: false,
        fetchMore: vi.fn(),
        refetch: vi.fn(),
        clearError: vi.fn(),
      });

      const { container } = render(<TrackList />);

      const separator = container.querySelector('span:contains("•")');
      expect(separator).toBeInTheDocument();
    });

    it('should render correct duration format', () => {
      const trackWithLongDuration: Track = {
        ...mockTrack1,
        duration: 3661, // 1 hour 1 minute 1 second
      };

      vi.mocked(useTracksQuery).mockReturnValue({
        data: [trackWithLongDuration],
        isLoading: false,
        error: null,
        total: 1,
        offset: 0,
        hasMore: false,
        fetchMore: vi.fn(),
        refetch: vi.fn(),
        clearError: vi.fn(),
      });

      render(<TrackList />);

      expect(screen.getByText('1:01:01')).toBeInTheDocument();
    });

    it('should skip album display if not provided', () => {
      const trackWithoutAlbum: Track = {
        ...mockTrack1,
        album: null as any,
      };

      vi.mocked(useTracksQuery).mockReturnValue({
        data: [trackWithoutAlbum],
        isLoading: false,
        error: null,
        total: 1,
        offset: 0,
        hasMore: false,
        fetchMore: vi.fn(),
        refetch: vi.fn(),
        clearError: vi.fn(),
      });

      render(<TrackList />);

      expect(screen.getByText('Artist One')).toBeInTheDocument();
      expect(screen.queryByText('Album One')).not.toBeInTheDocument();
    });
  });

  describe('selection and interaction', () => {
    it('should call onTrackSelect when track is clicked', () => {
      const mockOnTrackSelect = vi.fn();

      vi.mocked(useTracksQuery).mockReturnValue({
        data: [mockTrack1],
        isLoading: false,
        error: null,
        total: 1,
        offset: 0,
        hasMore: false,
        fetchMore: vi.fn(),
        refetch: vi.fn(),
        clearError: vi.fn(),
      });

      render(<TrackList onTrackSelect={mockOnTrackSelect} />);

      const trackItem = screen.getByText('First Song').closest('[role="button"]');
      fireEvent.click(trackItem!);

      expect(mockOnTrackSelect).toHaveBeenCalledWith(mockTrack1);
    });

    it('should highlight selected track', () => {
      const mockOnTrackSelect = vi.fn();

      vi.mocked(useTracksQuery).mockReturnValue({
        data: [mockTrack1, mockTrack2],
        isLoading: false,
        error: null,
        total: 2,
        offset: 0,
        hasMore: false,
        fetchMore: vi.fn(),
        refetch: vi.fn(),
        clearError: vi.fn(),
      });

      const { container } = render(
        <TrackList onTrackSelect={mockOnTrackSelect} />
      );

      const firstTrackItem = screen.getByText('First Song').closest('[role="button"]');
      fireEvent.click(firstTrackItem!);

      // Selected item should have aria-selected="true"
      expect(firstTrackItem).toHaveAttribute('aria-selected', 'true');

      const secondTrackItem = screen.getByText('Second Song').closest('[role="button"]');
      expect(secondTrackItem).toHaveAttribute('aria-selected', 'false');
    });

    it('should update selection when different track is clicked', () => {
      const mockOnTrackSelect = vi.fn();

      vi.mocked(useTracksQuery).mockReturnValue({
        data: [mockTrack1, mockTrack2],
        isLoading: false,
        error: null,
        total: 2,
        offset: 0,
        hasMore: false,
        fetchMore: vi.fn(),
        refetch: vi.fn(),
        clearError: vi.fn(),
      });

      render(<TrackList onTrackSelect={mockOnTrackSelect} />);

      const firstTrackItem = screen.getByText('First Song').closest('[role="button"]');
      fireEvent.click(firstTrackItem!);
      expect(mockOnTrackSelect).toHaveBeenCalledWith(mockTrack1);

      const secondTrackItem = screen.getByText('Second Song').closest('[role="button"]');
      fireEvent.click(secondTrackItem!);
      expect(mockOnTrackSelect).toHaveBeenCalledWith(mockTrack2);
    });
  });

  describe('infinite scroll', () => {
    it('should set up Intersection Observer on mount', () => {
      vi.mocked(useTracksQuery).mockReturnValue({
        data: [mockTrack1],
        isLoading: false,
        error: null,
        total: 100,
        offset: 0,
        hasMore: true,
        fetchMore: vi.fn(),
        refetch: vi.fn(),
        clearError: vi.fn(),
      });

      render(<TrackList />);

      expect(mockIntersectionObserver).toHaveBeenCalled();
    });

    it('should call fetchMore when sentinel is visible', async () => {
      const mockFetchMore = vi.fn().mockResolvedValue(undefined);

      vi.mocked(useTracksQuery).mockReturnValue({
        data: [mockTrack1],
        isLoading: false,
        error: null,
        total: 100,
        offset: 0,
        hasMore: true,
        fetchMore: mockFetchMore,
        refetch: vi.fn(),
        clearError: vi.fn(),
      });

      render(<TrackList />);

      // Simulate intersection observer callback
      const callback = mockIntersectionObserver.mock.calls[0][0];
      callback([{ isIntersecting: true }]);

      await waitFor(() => {
        expect(mockFetchMore).toHaveBeenCalled();
      });
    });

    it('should not fetch more if already loading', () => {
      const mockFetchMore = vi.fn();

      vi.mocked(useTracksQuery).mockReturnValue({
        data: [mockTrack1],
        isLoading: true,
        error: null,
        total: 100,
        offset: 0,
        hasMore: true,
        fetchMore: mockFetchMore,
        refetch: vi.fn(),
        clearError: vi.fn(),
      });

      render(<TrackList />);

      const callback = mockIntersectionObserver.mock.calls[0][0];
      callback([{ isIntersecting: true }]);

      // With isLoading=true, fetchMore should not be called
      expect(mockFetchMore).not.toHaveBeenCalled();
    });

    it('should not fetch more if hasMore is false', () => {
      const mockFetchMore = vi.fn();

      vi.mocked(useTracksQuery).mockReturnValue({
        data: [mockTrack1],
        isLoading: false,
        error: null,
        total: 1,
        offset: 0,
        hasMore: false,
        fetchMore: mockFetchMore,
        refetch: vi.fn(),
        clearError: vi.fn(),
      });

      render(<TrackList />);

      const callback = mockIntersectionObserver.mock.calls[0][0];
      callback([{ isIntersecting: true }]);

      expect(mockFetchMore).not.toHaveBeenCalled();
    });

    it('should disconnect observer on unmount', () => {
      const mockDisconnect = vi.fn();
      mockIntersectionObserver.mockReturnValue({
        observe: vi.fn(),
        unobserve: vi.fn(),
        disconnect: mockDisconnect,
      });

      vi.mocked(useTracksQuery).mockReturnValue({
        data: [mockTrack1],
        isLoading: false,
        error: null,
        total: 100,
        offset: 0,
        hasMore: true,
        fetchMore: vi.fn(),
        refetch: vi.fn(),
        clearError: vi.fn(),
      });

      const { unmount } = render(<TrackList />);
      unmount();

      expect(mockDisconnect).toHaveBeenCalled();
    });
  });

  describe('loading state', () => {
    it('should display loading message when loading', () => {
      vi.mocked(useTracksQuery).mockReturnValue({
        data: [mockTrack1],
        isLoading: true,
        error: null,
        total: 100,
        offset: 0,
        hasMore: true,
        fetchMore: vi.fn(),
        refetch: vi.fn(),
        clearError: vi.fn(),
      });

      render(<TrackList />);

      expect(screen.getByText(/Loading more tracks/i)).toBeInTheDocument();
    });

    it('should not display loading message when not loading', () => {
      vi.mocked(useTracksQuery).mockReturnValue({
        data: [mockTrack1],
        isLoading: false,
        error: null,
        total: 1,
        offset: 0,
        hasMore: false,
        fetchMore: vi.fn(),
        refetch: vi.fn(),
        clearError: vi.fn(),
      });

      render(<TrackList />);

      expect(screen.queryByText(/Loading more tracks/i)).not.toBeInTheDocument();
    });
  });

  describe('end of list', () => {
    it('should display end message when no more results', () => {
      vi.mocked(useTracksQuery).mockReturnValue({
        data: [mockTrack1, mockTrack2],
        isLoading: false,
        error: null,
        total: 2,
        offset: 0,
        hasMore: false,
        fetchMore: vi.fn(),
        refetch: vi.fn(),
        clearError: vi.fn(),
      });

      render(<TrackList />);

      expect(screen.getByText(/End of list/i)).toBeInTheDocument();
      expect(screen.getByText(/2 tracks/i)).toBeInTheDocument();
    });

    it('should not display end message when hasMore is true', () => {
      vi.mocked(useTracksQuery).mockReturnValue({
        data: [mockTrack1],
        isLoading: false,
        error: null,
        total: 100,
        offset: 0,
        hasMore: true,
        fetchMore: vi.fn(),
        refetch: vi.fn(),
        clearError: vi.fn(),
      });

      render(<TrackList />);

      expect(screen.queryByText(/End of list/i)).not.toBeInTheDocument();
    });

    it('should not display end message if no tracks loaded', () => {
      vi.mocked(useTracksQuery).mockReturnValue({
        data: [],
        isLoading: false,
        error: null,
        total: 0,
        offset: 0,
        hasMore: false,
        fetchMore: vi.fn(),
        refetch: vi.fn(),
        clearError: vi.fn(),
      });

      render(<TrackList />);

      expect(screen.queryByText(/End of list/i)).not.toBeInTheDocument();
    });
  });

  describe('error state', () => {
    it('should display error message on failure', () => {
      const mockError = {
        message: 'Failed to load tracks',
        code: 'LOAD_ERROR',
        status: 500,
      };

      vi.mocked(useTracksQuery).mockReturnValue({
        data: [],
        isLoading: false,
        error: mockError,
        total: 0,
        offset: 0,
        hasMore: false,
        fetchMore: vi.fn(),
        refetch: vi.fn(),
        clearError: vi.fn(),
      });

      render(<TrackList />);

      expect(screen.getByText('Failed to load tracks')).toBeInTheDocument();
      expect(screen.getByText('Failed to load tracks')).toBeInTheDocument();
    });
  });

  describe('empty state', () => {
    it('should display empty message when no tracks', () => {
      vi.mocked(useTracksQuery).mockReturnValue({
        data: [],
        isLoading: false,
        error: null,
        total: 0,
        offset: 0,
        hasMore: false,
        fetchMore: vi.fn(),
        refetch: vi.fn(),
        clearError: vi.fn(),
      });

      render(<TrackList />);

      expect(screen.getByText('No tracks found')).toBeInTheDocument();
    });

    it('should display search hint in empty state when searching', () => {
      vi.mocked(useTracksQuery).mockReturnValue({
        data: [],
        isLoading: false,
        error: null,
        total: 0,
        offset: 0,
        hasMore: false,
        fetchMore: vi.fn(),
        refetch: vi.fn(),
        clearError: vi.fn(),
      });

      render(<TrackList search="nonexistent" />);

      expect(screen.getByText('No tracks found')).toBeInTheDocument();
      expect(screen.getByText(/Try a different search/i)).toBeInTheDocument();
    });

    it('should not show empty state while loading', () => {
      vi.mocked(useTracksQuery).mockReturnValue({
        data: [],
        isLoading: true,
        error: null,
        total: 0,
        offset: 0,
        hasMore: true,
        fetchMore: vi.fn(),
        refetch: vi.fn(),
        clearError: vi.fn(),
      });

      render(<TrackList />);

      expect(screen.queryByText('No tracks found')).not.toBeInTheDocument();
    });
  });

  describe('props and options', () => {
    it('should pass search prop to useTracksQuery', () => {
      vi.mocked(useTracksQuery).mockReturnValue({
        data: [],
        isLoading: false,
        error: null,
        total: 0,
        offset: 0,
        hasMore: false,
        fetchMore: vi.fn(),
        refetch: vi.fn(),
        clearError: vi.fn(),
      });

      render(<TrackList search="test" />);

      expect(vi.mocked(useTracksQuery)).toHaveBeenCalledWith(
        expect.objectContaining({
          search: 'test',
        })
      );
    });

    it('should pass limit prop to useTracksQuery', () => {
      vi.mocked(useTracksQuery).mockReturnValue({
        data: [],
        isLoading: false,
        error: null,
        total: 0,
        offset: 0,
        hasMore: false,
        fetchMore: vi.fn(),
        refetch: vi.fn(),
        clearError: vi.fn(),
      });

      render(<TrackList limit={25} />);

      expect(vi.mocked(useTracksQuery)).toHaveBeenCalledWith(
        expect.objectContaining({
          limit: 25,
        })
      );
    });

    it('should use default limit when not provided', () => {
      vi.mocked(useTracksQuery).mockReturnValue({
        data: [],
        isLoading: false,
        error: null,
        total: 0,
        offset: 0,
        hasMore: false,
        fetchMore: vi.fn(),
        refetch: vi.fn(),
        clearError: vi.fn(),
      });

      render(<TrackList />);

      expect(vi.mocked(useTracksQuery)).toHaveBeenCalledWith(
        expect.objectContaining({
          limit: 50,
        })
      );
    });
  });

  describe('accessibility', () => {
    it('should have role="button" on track items', () => {
      vi.mocked(useTracksQuery).mockReturnValue({
        data: [mockTrack1],
        isLoading: false,
        error: null,
        total: 1,
        offset: 0,
        hasMore: false,
        fetchMore: vi.fn(),
        refetch: vi.fn(),
        clearError: vi.fn(),
      });

      render(<TrackList />);

      const trackItem = screen.getByText('First Song').closest('[role="button"]');
      expect(trackItem).toHaveAttribute('role', 'button');
    });

    it('should have tabIndex on track items', () => {
      vi.mocked(useTracksQuery).mockReturnValue({
        data: [mockTrack1],
        isLoading: false,
        error: null,
        total: 1,
        offset: 0,
        hasMore: false,
        fetchMore: vi.fn(),
        refetch: vi.fn(),
        clearError: vi.fn(),
      });

      render(<TrackList />);

      const trackItem = screen.getByText('First Song').closest('[role="button"]');
      expect(trackItem).toHaveAttribute('tabIndex', '0');
    });

    it('should have aria-selected attribute', () => {
      vi.mocked(useTracksQuery).mockReturnValue({
        data: [mockTrack1],
        isLoading: false,
        error: null,
        total: 1,
        offset: 0,
        hasMore: false,
        fetchMore: vi.fn(),
        refetch: vi.fn(),
        clearError: vi.fn(),
      });

      render(<TrackList />);

      const trackItem = screen.getByText('First Song').closest('[role="button"]');
      expect(trackItem).toHaveAttribute('aria-selected');
    });
  });
});
