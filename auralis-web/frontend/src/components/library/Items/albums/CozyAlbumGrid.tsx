/**
 * CozyAlbumGrid Component
 *
 * Displays albums in a responsive grid layout with infinite scroll.
 * Uses TanStack Query for data fetching + IntersectionObserver for scroll detection.
 *
 * Grid Layout:
 * - Responsive CSS Grid (auto-fills columns based on 200px minimum width)
 * - Infinite scroll via sentinel element + IntersectionObserver
 * - TanStack Query handles caching, deduplication, and loading states
 */

import React, { useEffect, useRef } from 'react';
import { EmptyState } from '../../../shared/ui/feedback';
import { AlbumGridLoadingState } from './AlbumGridLoadingState';
import { useInfiniteAlbums } from '@/hooks/library/useInfiniteAlbums';
import { AlbumCard } from '@/components/album/AlbumCard/AlbumCard';

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
  const loadMoreRef = useRef<HTMLDivElement>(null);

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

  // Intersection Observer for infinite scroll
  useEffect(() => {
    if (!loadMoreRef.current || !hasNextPage || isFetchingNextPage) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) {
          fetchNextPage();
        }
      },
      { threshold: 0.1 }
    );

    observer.observe(loadMoreRef.current);
    return () => observer.disconnect();
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);

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

  // CSS Grid rendering with infinite scroll
  return (
    <div
      style={{
        height: '100%',
        overflow: 'auto',
        padding: '16px',
      }}
    >
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
          gap: '16px',
          width: '100%',
        }}
      >
        {albums.map((album) => (
          <AlbumCard
            key={album.id}
            albumId={album.id}
            title={album.title}
            artist={album.artist}
            hasArtwork={!!album.artworkUrl}
            trackCount={album.trackCount}
            duration={album.totalDuration}
            year={album.year}
            onClick={() => onAlbumClick?.(album.id)}
          />
        ))}
      </div>

      {/* Sentinel element for infinite scroll */}
      {hasNextPage && (
        <div
          ref={loadMoreRef}
          style={{
            padding: '16px',
            textAlign: 'center',
            minHeight: '40px',
          }}
        >
          {isFetchingNextPage ? 'Loading more albums...' : '\u00A0'}
        </div>
      )}
    </div>
  );
};

export default CozyAlbumGrid;
