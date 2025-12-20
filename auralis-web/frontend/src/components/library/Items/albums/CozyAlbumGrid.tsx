/**
 * CozyAlbumGrid Component
 *
 * Displays albums in a responsive grid layout with infinite scroll.
 * Uses unified pagination pattern: useAlbumsQuery + useInfiniteScroll
 *
 * Extracted modules:
 * - AlbumGridLoadingState - Loading skeleton display
 * - AlbumGridContent - Album grid rendering
 */

import React, { useRef } from 'react';
import { EmptyState } from '../../../shared/ui/feedback';
import { AlbumGridLoadingState } from './AlbumGridLoadingState';
import { AlbumGridContent } from './AlbumGridContent';
import { useAlbumsQuery } from '@/hooks/library';
import { useInfiniteScroll } from '@/hooks/shared';

interface CozyAlbumGridProps {
  onAlbumClick?: (albumId: number) => void;
}

/**
 * CozyAlbumGrid - Album grid with pagination
 *
 * Uses unified pagination pattern consistent with Tracks view:
 * - useAlbumsQuery: Data fetching with pagination
 * - useInfiniteScroll: IntersectionObserver-based scroll detection
 */
export const CozyAlbumGrid: React.FC<CozyAlbumGridProps> = ({ onAlbumClick }) => {
  const containerRef = useRef<HTMLDivElement>(null);

  // Data fetching with pagination
  const {
    data: albums,
    isLoading,
    error,
    total: totalAlbums,
    hasMore,
    fetchMore,
  } = useAlbumsQuery({ limit: 50 });

  // Infinite scroll detection - returns ref to attach to sentinel element
  const { observerTarget, isFetching } = useInfiniteScroll({
    threshold: 0.8,
    onLoadMore: fetchMore,
    hasMore,
    isLoading,
  });

  // Handle album click
  const handleAlbumClick = (albumId: number) => {
    if (onAlbumClick) {
      onAlbumClick(albumId);
    }
  };

  // Loading state
  if (isLoading && albums.length === 0) {
    return <AlbumGridLoadingState />;
  }

  // Error state
  if (error) {
    return (
      <EmptyState
        title="Error Loading Albums"
        description={error.message || 'Failed to load albums'}
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
      isLoadingMore={isFetching}
      totalAlbums={totalAlbums}
      containerRef={containerRef}
      loadMoreTriggerRef={observerTarget}
      onAlbumClick={handleAlbumClick}
    />
  );
};

export default CozyAlbumGrid;
