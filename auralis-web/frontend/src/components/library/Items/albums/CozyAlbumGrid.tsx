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
 *
 * Fingerprint Integration:
 * - Batch fetches fingerprints for all visible albums
 * - Generates unique sonic-identity gradients for placeholders
 * - Falls back to hash-based gradients if fingerprints unavailable
 */

import React, { useEffect, useRef, useMemo } from 'react';
import { EmptyState } from '../../../shared/ui/feedback';
import { AlbumGridLoadingState } from './AlbumGridLoadingState';
import { useInfiniteAlbums } from '@/hooks/library/useInfiniteAlbums';
import { useAlbumFingerprints } from '@/hooks/fingerprint/useAlbumFingerprint';
import { AlbumCard } from '@/components/album/AlbumCard/AlbumCard';
import { tokens } from '@/design-system';

interface CozyAlbumGridProps {
  onAlbumClick?: (albumId: number) => void;
  onAlbumHover?: (albumId: number) => void;
  onAlbumHoverEnd?: () => void;
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
export const CozyAlbumGrid: React.FC<CozyAlbumGridProps> = ({
  onAlbumClick,
  onAlbumHover,
  onAlbumHoverEnd,
}) => {
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

  // Extract album IDs for batch fingerprint fetching
  const albumIds = useMemo(() => albums.map(album => album.id), [albums]);

  // Batch fetch fingerprints for all albums
  const { fingerprints } = useAlbumFingerprints(albumIds);

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

  // CSS Grid rendering with infinite scroll (Design Language v1.2.0 §4.3)
  return (
    <div
      style={{
        height: '100%',
        overflow: 'auto',
        padding: tokens.spacing.group,                    // 16px - organic group spacing
      }}
    >
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, 200px)',
          gap: tokens.spacing.group,                      // 16px - organic group spacing
          width: '100%',
        }}
      >
        {albums.map((album) => {
          // Get fingerprint for this album (if available)
          const fingerprint = fingerprints.get(album.id) ?? undefined;

          return (
            <AlbumCard
              key={album.id}
              albumId={album.id}
              title={album.title}
              artist={album.artist}
              hasArtwork={!!album.artworkUrl}
              trackCount={album.trackCount}
              duration={album.totalDuration}
              year={album.year}
              fingerprint={fingerprint}
              onClick={() => onAlbumClick?.(album.id)}
              onHoverEnter={onAlbumHover}
              onHoverLeave={onAlbumHoverEnd}
            />
          );
        })}
      </div>

      {/* Sentinel element for infinite scroll */}
      {hasNextPage && (
        <div
          ref={loadMoreRef}
          style={{
            padding: tokens.spacing.group,                  // 16px - organic group spacing
            textAlign: 'center',
            minHeight: tokens.spacing.xxl,                  // 40px - vertical space
          }}
        >
          {isFetchingNextPage ? 'Loading more albums...' : '\u00A0'}
        </div>
      )}
    </div>
  );
};

export default CozyAlbumGrid;
