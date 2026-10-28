/**
 * CozyArtistList Component
 *
 * Main orchestration component for artist list view with infinite scroll
 * pagination, alphabetic grouping, and context menu support.
 *
 * Features:
 * - Infinite scroll pagination via react-infinite-scroll-component
 * - Alphabetically grouped artist sections
 * - Context menu with artist actions
 * - Loading skeleton and loading indicator
 * - End-of-list feedback
 *
 * Uses unified pagination pattern:
 * - useArtistsQuery: Data fetching with pagination
 * - react-infinite-scroll-component: Battle-tested infinite scroll
 * - useGroupedArtists: Alphabetical grouping logic
 * - useContextMenuActions: Context menu state and actions
 * - ArtistListContent: Rendering component
 * - ArtistListEmptyState: Empty/error state
 *
 * Usage:
 * ```tsx
 * <CozyArtistList onArtistClick={handleArtistClick} />
 * ```
 */

import { MouseEvent, useCallback, useState } from 'react';
import { ArtistListLoading } from './ArtistListLoading';
import { ArtistListEmptyState } from './ArtistListEmptyState';
import { ArtistListContent } from './ArtistListContent';
import { ArtistInfoModal } from './ArtistInfoModal';
import { useArtistsQuery } from '@/hooks/library';
import { useGroupedArtists } from '@/hooks/shared';
import { useContextMenuActions } from './useContextMenuActions';
import { useContextMenu } from '@/components/shared/ContextMenu';
import type { Artist } from '@/types/domain';

interface CozyArtistListProps {
  onArtistClick?: (artistId: number, artistName: string) => void;
  /** Server-side search term (#5866). */
  search?: string;
}

export const CozyArtistList = ({ onArtistClick, search }: CozyArtistListProps) => {
  const [contextMenuArtist, setContextMenuArtist] = useState<Artist | null>(null);

  // Data fetching with pagination
  const {
    data: artists,
    isLoading,
    isLoadingMore,
    error,
    loadMoreError,
    total: totalArtists,
    hasMore,
    fetchMore,
    refetch,
  } = useArtistsQuery({ limit: 50, search });

  // Artist grouping by first letter
  const { groupedArtists, sortedLetters } = useGroupedArtists(artists);

  // Context menu
  const { contextMenuState, handleContextMenu, handleCloseContextMenu } = useContextMenu();

  const handleArtistClick = useCallback((artist: Artist) => {
    if (onArtistClick) {
      onArtistClick(artist.id, artist.name);
    }
  }, [onArtistClick]);

  const handleContextMenuOpen = useCallback((artist: Artist, event: MouseEvent) => {
    event.preventDefault();
    event.stopPropagation();
    setContextMenuArtist(artist);
    handleContextMenu(event);
  }, [handleContextMenu]);

  // Stable identity so opening/closing the menu does not hand
  // ArtistListContent a fresh prop on every render (#5389).
  const handleContextMenuClose = useCallback(() => {
    setContextMenuArtist(null);
    handleCloseContextMenu();
  }, [handleCloseContextMenu]);

  const { actions: contextActions, modal: infoModal } = useContextMenuActions({
    artist: contextMenuArtist,
    onArtistClick,
  });

  if (isLoading && artists.length === 0) {
    return <ArtistListLoading />;
  }

  // `error` is the current query's own failure (stale rows from a previous
  // search must not stay up); a failed later page is `loadMoreError` instead,
  // which keeps the loaded rows behind an inline Retry (#5870).
  if (error || artists.length === 0) {
    return (
      <ArtistListEmptyState
        loading={isLoading}
        error={error?.message ?? null}
        onRetry={() => void refetch()}
      />
    );
  }

  return (
    <>
      <ArtistListContent
        artists={artists}
        totalArtists={totalArtists}
        isLoadingMore={isLoadingMore}
        hasMore={hasMore}
        fetchMore={fetchMore}
        loadMoreFailed={loadMoreError !== null}
        groupedArtists={groupedArtists}
        sortedLetters={sortedLetters}
        contextMenuState={contextMenuState}
        contextActions={contextActions}
        onArtistClick={handleArtistClick}
        onContextMenuOpen={handleContextMenuOpen}
        onContextMenuClose={handleContextMenuClose}
      />
      <ArtistInfoModal
        open={infoModal.open}
        artist={infoModal.artist}
        onClose={infoModal.onClose}
      />
    </>
  );
};

export default CozyArtistList;
