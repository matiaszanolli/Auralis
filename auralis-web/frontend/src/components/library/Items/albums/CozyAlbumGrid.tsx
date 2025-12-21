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

import React, { useEffect, useRef } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import { EmptyState } from '../../../shared/ui/feedback';
import { AlbumGridLoadingState } from './AlbumGridLoadingState';
import { useInfiniteAlbums } from '@/hooks/library/useInfiniteAlbums';
import { AlbumCard } from './AlbumCard';

interface CozyAlbumGridProps {
  onAlbumClick?: (albumId: number) => void;
}

/**
 * CozyAlbumGrid - Album grid with infinite scroll
 *
 * Uses TanStack Query's useInfiniteQuery for robust infinite scroll:
 * - Automatic request deduplication
 * - Built-in loading states
 * - Cache management
 * - No race conditions
 */
export const CozyAlbumGrid: React.FC<CozyAlbumGridProps> = ({ onAlbumClick }) => {
  const parentRef = useRef<HTMLDivElement>(null);

  // Infinite query with TanStack Query
  const {
    data,
    isLoading,
    error,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useInfiniteAlbums({ limit: 50 });

  // Flatten all pages into single array
  const albums = data?.pages.flatMap(page => page.albums) ?? [];
  const totalAlbums = data?.pages[0]?.total ?? 0;

  // Virtualizer for the full list (represents ALL 3866 albums)
  const rowVirtualizer = useVirtualizer({
    count: totalAlbums, // Total count, not just loaded
    getScrollElement: () => parentRef.current,
    estimateSize: () => 220, // Estimated album card height
    overscan: 5,
  });

  // Fetch more when scrolling approaches unloaded items
  useEffect(() => {
    const [lastItem] = [...rowVirtualizer.getVirtualItems()].reverse();

    if (!lastItem) return;

    // If we're scrolling near the end of loaded items, fetch more
    if (
      lastItem.index >= albums.length - 1 &&
      hasNextPage &&
      !isFetchingNextPage
    ) {
      fetchNextPage();
    }
  }, [
    hasNextPage,
    fetchNextPage,
    albums.length,
    isFetchingNextPage,
    rowVirtualizer.getVirtualItems(),
  ]);

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

  // Virtualized grid rendering
  return (
    <div
      ref={parentRef}
      style={{
        height: '100%',
        overflow: 'auto',
      }}
    >
      <div
        style={{
          height: `${rowVirtualizer.getTotalSize()}px`,
          width: '100%',
          position: 'relative',
        }}
      >
        {rowVirtualizer.getVirtualItems().map((virtualRow) => {
          const album = albums[virtualRow.index];

          // Show placeholder if album not loaded yet
          if (!album) {
            return (
              <div
                key={virtualRow.index}
                style={{
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  width: '100%',
                  height: `${virtualRow.size}px`,
                  transform: `translateY(${virtualRow.start}px)`,
                }}
              >
                <div style={{ padding: '8px', opacity: 0.5 }}>
                  Loading album {virtualRow.index + 1}...
                </div>
              </div>
            );
          }

          return (
            <div
              key={virtualRow.key}
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                width: '200px',
                height: `${virtualRow.size}px`,
                transform: `translateY(${virtualRow.start}px)`,
              }}
            >
              <AlbumCard
                album={album}
                onClick={() => onAlbumClick?.(album.id)}
              />
            </div>
          );
        })}
      </div>
      {isFetchingNextPage && (
        <div style={{ padding: '16px', textAlign: 'center' }}>
          Loading more albums...
        </div>
      )}
    </div>
  );
};

export default CozyAlbumGrid;
