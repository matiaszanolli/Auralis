import { useState, useEffect, useRef } from 'react';
import { useContextMenu } from '../shared/ContextMenu';
import { useToast } from '../shared/Toast';

interface Artist {
  id: number;
  name: string;
  album_count?: number;
  track_count?: number;
}

interface UseArtistListPaginationProps {
  onArtistClick?: (artistId: number, artistName: string) => void;
}

interface UseArtistListPaginationReturn {
  artists: Artist[];
  loading: boolean;
  error: string | null;
  hasMore: boolean;
  totalArtists: number;
  isLoadingMore: boolean;
  containerRef: React.RefObject<HTMLDivElement>;
  loadMoreTriggerRef: React.RefObject<HTMLDivElement>;
  contextMenuState: any;
  contextMenuArtist: Artist | null;
  handleContextMenu: (e: React.MouseEvent) => void;
  handleCloseContextMenu: () => void;
  handleArtistClick: (artist: Artist) => void;
  handleContextMenuOpen: (e: React.MouseEvent, artist: Artist) => void;
  groupedArtists: Record<string, Artist[]>;
  sortedLetters: string[];
}

/**
 * useArtistListPagination - Pagination, grouping, and context menu logic for artist list
 *
 * Manages:
 * - Infinite scroll with offset-based pagination (50 per page)
 * - Artist grouping by first letter
 * - Context menu state and actions
 * - Data fetching and error handling
 *
 * Returns:
 * - artists: All loaded artists
 * - loading: Initial load state
 * - error: Error message if fetch fails
 * - hasMore: Whether more artists available
 * - totalArtists: Total count from API
 * - isLoadingMore: Loading state for pagination
 * - Refs: containerRef, loadMoreTriggerRef
 * - Context menu: state, handlers, artist
 * - Handlers: handleArtistClick, handleContextMenuOpen, handleCloseContextMenu
 * - Grouping: groupedArtists, sortedLetters
 */
export const useArtistListPagination = ({
  onArtistClick
}: UseArtistListPaginationProps): UseArtistListPaginationReturn => {
  const [artists, setArtists] = useState<Artist[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const [totalArtists, setTotalArtists] = useState(0);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [contextMenuArtist, setContextMenuArtist] = useState<Artist | null>(null);

  // Refs for scroll container and infinite scroll trigger
  const containerRef = useRef<HTMLDivElement>(null);
  const loadMoreTriggerRef = useRef<HTMLDivElement>(null);

  // Context menu and toast hooks
  const { contextMenuState, handleContextMenu, handleCloseContextMenu: closeContextMenu } = useContextMenu();
  const { success, info } = useToast();

  // Initial fetch on mount
  useEffect(() => {
    fetchArtists(true);
  }, []);

  // Infinite scroll detection
  useEffect(() => {
    const handleScroll = () => {
      if (!hasMore || isLoadingMore || loading) return;

      const triggerElement = loadMoreTriggerRef.current;
      if (!triggerElement) return;

      const rect = triggerElement.getBoundingClientRect();
      const viewportHeight = window.innerHeight;
      const isNearViewport = rect.top < viewportHeight + 2000;

      if (isNearViewport) {
        loadMore();
      }
    };

    // Find scrollable parent
    let scrollableParent = containerRef.current?.parentElement;
    while (scrollableParent) {
      const overflowY = window.getComputedStyle(scrollableParent).overflowY;
      if (overflowY === 'auto' || overflowY === 'scroll') break;
      scrollableParent = scrollableParent.parentElement;
    }

    if (scrollableParent) {
      scrollableParent.addEventListener('scroll', handleScroll);
      handleScroll();
      return () => {
        scrollableParent.removeEventListener('scroll', handleScroll);
      };
    }
  }, [hasMore, isLoadingMore, loading, offset, artists.length]);

  const fetchArtists = async (resetPagination = false) => {
    if (resetPagination) {
      setLoading(true);
      setOffset(0);
      setArtists([]);
    } else {
      setIsLoadingMore(true);
    }

    setError(null);

    try {
      const limit = 50;
      const currentOffset = resetPagination ? 0 : offset;

      const response = await fetch(`/api/artists?limit=${limit}&offset=${currentOffset}`);
      if (!response.ok) {
        throw new Error('Failed to fetch artists');
      }

      const data = await response.json();

      setHasMore(data.has_more || false);
      setTotalArtists(data.total || 0);

      if (resetPagination) {
        setArtists(data.artists || []);
      } else {
        const newArtists = data.artists || [];
        setArtists(prev => {
          const existingIds = new Set(prev.map((a: Artist) => a.id));
          return [...prev, ...newArtists.filter((a: Artist) => !existingIds.has(a.id))];
        });
      }
    } catch (err) {
      console.error('Error fetching artists:', err);
      setError(err instanceof Error ? err.message : 'Failed to load artists');
    } finally {
      setLoading(false);
      setIsLoadingMore(false);
    }
  };

  const loadMore = async () => {
    if (isLoadingMore || !hasMore) {
      return;
    }

    const limit = 50;
    const newOffset = offset + limit;
    setOffset(newOffset);
    await fetchArtists(false);
  };

  const handleArtistClick = (artist: Artist) => {
    if (onArtistClick) {
      onArtistClick(artist.id, artist.name);
    }
  };

  const handleContextMenuOpen = (e: React.MouseEvent, artist: Artist) => {
    e.preventDefault();
    e.stopPropagation();
    setContextMenuArtist(artist);
    handleContextMenu(e);
  };

  const handleCloseContextMenu = () => {
    setContextMenuArtist(null);
    closeContextMenu();
  };

  // Group artists by first letter
  const groupedArtists = artists.reduce((acc, artist) => {
    const initial = artist.name.charAt(0).toUpperCase();
    if (!acc[initial]) {
      acc[initial] = [];
    }
    acc[initial].push(artist);
    return acc;
  }, {} as Record<string, Artist[]>);

  const sortedLetters = Object.keys(groupedArtists).sort();

  return {
    artists,
    loading,
    error,
    hasMore,
    totalArtists,
    isLoadingMore,
    containerRef,
    loadMoreTriggerRef,
    contextMenuState,
    contextMenuArtist,
    handleContextMenu,
    handleCloseContextMenu,
    handleArtistClick,
    handleContextMenuOpen,
    groupedArtists,
    sortedLetters
  };
};

export default useArtistListPagination;
