/**
 * CozyAlbumGrid Component (Refactored)
 *
 * Displays albums in a responsive grid layout with infinite scroll.
 * Refactored from 232 lines using extracted components and hooks.
 *
 * Extracted modules:
 * - useAlbumGridPagination - Data fetching and pagination
 * - useAlbumGridScroll - Infinite scroll logic
 * - AlbumGridLoadingState - Loading skeleton display
 * - AlbumGridContent - Album grid rendering
 */

import React, { useEffect } from 'react';
import { EmptyState } from '../../shared/ui/feedback';
import { AlbumGridLoadingState } from './AlbumGridLoadingState';
import { AlbumGridContent } from './AlbumGridContent';
import { useAlbumGridPagination } from './useAlbumGridPagination';
import { useAlbumGridScroll } from './useAlbumGridScroll';

interface CozyAlbumGridProps {
  onAlbumClick?: (albumId: number) => void;
}

/**
 * CozyAlbumGrid - Main orchestrator component
 *
 * Manages:
 * - Album data fetching with pagination
 * - Infinite scroll detection
 * - Loading and error states
 * - Grid rendering with album cards
 */
export const CozyAlbumGrid: React.FC<CozyAlbumGridProps> = ({ onAlbumClick }) => {
  console.log('[CozyAlbumGrid] Rendered');

  // Pagination logic
  const {
    albums,
    loading,
    error,
    offset,
    hasMore,
    totalAlbums,
    isLoadingMore,
    fetchAlbums,
    loadMore,
  } = useAlbumGridPagination();

  // Scroll detection
  const { containerRef, loadMoreTriggerRef } = useAlbumGridScroll({
    hasMore,
    isLoadingMore,
    loading,
    offset,
    albumsLength: albums.length,
    onLoadMore: loadMore,
  });

  // Initial fetch
  useEffect(() => {
    fetchAlbums(true);
  }, []);

  // Handle click
  const handleAlbumClick = (albumId: number) => {
    if (onAlbumClick) {
      onAlbumClick(albumId);
    }
  };

  // Loading state
  if (loading) {
    return <AlbumGridLoadingState />;
  }

  // Error state
  if (error) {
    return (
      <EmptyState
        title="Error Loading Albums"
        description={error}
      />
    );
  }

  // Empty state
  if (albums.length === 0) {
    return (
      <EmptyState
        title="No Albums Yet"
        description="Your album library will appear here once you scan your music folder"
      />
    );
  }

  // Render grid
  return (
    <AlbumGridContent
      albums={albums}
      hasMore={hasMore}
      isLoadingMore={isLoadingMore}
      totalAlbums={totalAlbums}
      containerRef={containerRef}
      loadMoreTriggerRef={loadMoreTriggerRef}
      onAlbumClick={handleAlbumClick}
    />
  );
};

export default CozyAlbumGrid;
