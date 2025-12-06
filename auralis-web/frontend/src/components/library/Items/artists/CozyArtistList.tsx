/**
 * CozyArtistList Component
 *
 * Main orchestration component for artist list view with infinite scroll
 * pagination, alphabetic grouping, and context menu support.
 *
 * Features:
 * - Infinite scroll pagination via IntersectionObserver
 * - Alphabetically grouped artist sections
 * - Context menu with artist actions
 * - Loading skeleton and loading indicator
 * - End-of-list feedback
 *
 * Uses unified pagination pattern:
 * - useArtistsQuery: Data fetching with pagination
 * - useInfiniteScroll: IntersectionObserver-based scroll detection
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

import React, { useCallback, useRef, useState } from 'react';
import { ArtistListLoading } from './ArtistListLoading';
import { ArtistListEmptyState } from './ArtistListEmptyState';
import { ArtistListContent } from './ArtistListContent';
import { ArtistInfoModal } from './ArtistInfoModal';
import { useArtistsQuery } from '@/hooks/library';
import { useInfiniteScroll, useGroupedArtists } from '@/hooks/shared';
import { useContextMenuActions } from './useContextMenuActions';
import { useContextMenu } from '../../shared/ContextMenu';
import type { Artist } from '@/types/domain';

interface CozyArtistListProps {
  onArtistClick?: (artistId: number, artistName: string) => void;
}

export const CozyArtistList: React.FC<CozyArtistListProps> = ({ onArtistClick }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const loadMoreTriggerRef = useRef<HTMLDivElement>(null);
  const [contextMenuArtist, setContextMenuArtist] = useState<Artist | null>(null);

  // Data fetching with pagination
  const {
    data: artists,
    isLoading,
    error,
    total: totalArtists,
    hasMore,
    fetchMore,
  } = useArtistsQuery({ limit: 50 });

  // Artist grouping by first letter
  const { groupedArtists, sortedLetters } = useGroupedArtists(artists);

  // Infinite scroll detection
  useInfiniteScroll({
    ref: loadMoreTriggerRef,
    threshold: 0.8,
    onLoadMore: fetchMore,
    hasMore,
    isLoading,
  });

  // Context menu
  const { contextMenuState, handleContextMenu, handleCloseContextMenu } = useContextMenu();

  const handleArtistClick = useCallback((artist: Artist) => {
    if (onArtistClick) {
      onArtistClick(artist.id, artist.name);
    }
  }, [onArtistClick]);

  const handleContextMenuOpen = useCallback((event: React.MouseEvent, artist: Artist) => {
    event.preventDefault();
    event.stopPropagation();
    setContextMenuArtist(artist);
    handleContextMenu(event);
  }, [handleContextMenu]);

  const { actions: contextActions, modal: infoModal } = useContextMenuActions({
    artist: contextMenuArtist,
    onArtistClick,
  });

  if (isLoading && artists.length === 0) {
    return <ArtistListLoading />;
  }

  const emptyState = (
    <ArtistListEmptyState loading={isLoading} error={error?.message} />
  );

  if (error || artists.length === 0) {
    return emptyState;
  }

  return (
    <>
      <ArtistListContent
        artists={artists}
        totalArtists={totalArtists}
        isLoadingMore={isLoading && artists.length > 0}
        hasMore={hasMore}
        containerRef={containerRef}
        loadMoreTriggerRef={loadMoreTriggerRef}
        groupedArtists={groupedArtists}
        sortedLetters={sortedLetters}
        contextMenuState={contextMenuState}
        contextActions={contextActions}
        onArtistClick={handleArtistClick}
        onContextMenuOpen={handleContextMenuOpen}
        onContextMenuClose={() => {
          setContextMenuArtist(null);
          handleCloseContextMenu();
        }}
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
