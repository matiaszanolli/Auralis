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
 * - Era-based grouping (e.g., "1978 - 1982") for temporal organization
 *
 * Fingerprint Integration:
 * - Batch fetches fingerprints for all visible albums
 * - Generates unique sonic-identity gradients for placeholders
 * - Falls back to hash-based gradients if fingerprints unavailable
 */

import React, { useEffect, useRef, useMemo } from 'react';
import { EmptyState } from '../../../shared/ui/feedback';
import { AlbumGridLoadingState } from './AlbumGridLoadingState';
import { EraSection } from './EraSection';
import { useInfiniteAlbums } from '@/hooks/library/useInfiniteAlbums';
import { useAlbumFingerprints } from '@/hooks/fingerprint/useAlbumFingerprint';
import { groupAlbumsByEra } from '@/utils/eraGrouping';
import { tokens } from '@/design-system';

interface CozyAlbumGridProps {
  onAlbumClick?: (albumId: number) => void;
  onAlbumHover?: (albumId: number, albumTitle?: string, albumArtist?: string) => void;
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

  // Group albums by era (5-year spans)
  const eraGroups = useMemo(() => groupAlbumsByEra(albums), [albums]);

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

  // Era-grouped rendering with infinite scroll (Design Language v1.2.0 §4.3)
  return (
    <div
      style={{
        height: '100%',
        overflow: 'auto',
        padding: tokens.spacing.group,                    // 16px - organic group spacing
      }}
    >
      {/* Era-grouped album sections */}
      {eraGroups.map((eraGroup) => (
        <EraSection
          key={eraGroup.label}
          label={eraGroup.label}
          albums={eraGroup.albums}
          fingerprints={fingerprints}
          onAlbumClick={onAlbumClick}
          onAlbumHover={onAlbumHover}
          onAlbumHoverEnd={onAlbumHoverEnd}
        />
      ))}

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
