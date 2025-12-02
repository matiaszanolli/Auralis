/**
 * CozyArtistList Component
 *
 * Main orchestration component for artist list view with infinite scroll
 * pagination, alphabetic grouping, and context menu support.
 *
 * Features:
 * - Infinite scroll pagination (2000px threshold)
 * - Alphabetically grouped artist sections
 * - Context menu with artist actions
 * - Loading skeleton and loading indicator
 * - End-of-list feedback
 *
 * Uses:
 * - useArtistListPagination hook for data and pagination
 * - useContextMenuActions hook for context menu
 * - ArtistListContent component for rendering
 * - ArtistListEmptyState component for empty/error states
 *
 * Usage:
 * ```tsx
 * <CozyArtistList onArtistClick={handleArtistClick} />
 * ```
 */

import React, { useCallback } from 'react';
import { ArtistListLoading } from './ArtistListLoading';
import { ArtistListEmptyState } from './ArtistListEmptyState';
import { ArtistListContent } from './ArtistListContent';
import { useArtistListPagination } from '../Hooks/useArtistListPagination';
import { useContextMenuActions } from './useContextMenuActions';

interface CozyArtistListProps {
  onArtistClick?: (artistId: number, artistName: string) => void;
}

export const CozyArtistList: React.FC<CozyArtistListProps> = ({ onArtistClick }) => {
  const {
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
    handleCloseContextMenu,
    handleArtistClick,
    handleContextMenuOpen,
    groupedArtists,
    sortedLetters,
  } = useArtistListPagination({ onArtistClick });

  // Adapt the hook's handler signatures to what ArtistListContent expects
  const adaptedArtistClickHandler = useCallback((artist: { id: number; name: string; album_count?: number; track_count?: number }) => {
    handleArtistClick(artist);
  }, [handleArtistClick]);

  const adaptedContextMenuOpen = useCallback((artist: { id: number; name: string; album_count?: number; track_count?: number }, event: React.MouseEvent) => {
    handleContextMenuOpen(event, artist);
  }, [handleContextMenuOpen]);

  const contextActions = useContextMenuActions({
    artist: contextMenuArtist,
    onArtistClick,
  });

  if (loading) {
    return <ArtistListLoading />;
  }

  const emptyState = (
    <ArtistListEmptyState loading={loading} error={error} />
  );

  if (error || artists.length === 0) {
    return emptyState;
  }

  return (
    <ArtistListContent
      artists={artists}
      totalArtists={totalArtists}
      isLoadingMore={isLoadingMore}
      hasMore={hasMore}
      containerRef={containerRef}
      loadMoreTriggerRef={loadMoreTriggerRef}
      groupedArtists={groupedArtists}
      sortedLetters={sortedLetters}
      contextMenuState={contextMenuState}
      contextActions={contextActions}
      onArtistClick={adaptedArtistClickHandler}
      onContextMenuOpen={adaptedContextMenuOpen}
      onContextMenuClose={handleCloseContextMenu}
    />
  );
};

export default CozyArtistList;
