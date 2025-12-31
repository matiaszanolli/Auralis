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
 * - Multiple sort modes: A-Z (default), Year, Era-based grouping
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
import { AlbumCard } from '@/components/album/AlbumCard/AlbumCard';
import { useInfiniteAlbums } from '@/hooks/library/useInfiniteAlbums';
import { useAlbumFingerprints } from '@/hooks/fingerprint/useAlbumFingerprint';
import { groupAlbumsByEra } from '@/utils/eraGrouping';
import { tokens } from '@/design-system';

/** Sort options for album grid */
export type AlbumSortOption = 'az' | 'year' | 'era';

interface CozyAlbumGridProps {
  onAlbumClick?: (albumId: number) => void;
  onAlbumHover?: (albumId: number, albumTitle?: string, albumArtist?: string) => void;
  onAlbumHoverEnd?: () => void;
  /** Sort mode: 'az' (alphabetical), 'year' (newest first), 'era' (grouped by era) */
  sortBy?: AlbumSortOption;
}

/**
 * CozyAlbumGrid - Album grid with infinite scroll and sorting
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
  sortBy = 'az',
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

  // Sort albums based on sortBy option
  const sortedAlbums = useMemo(() => {
    if (sortBy === 'era') {
      // Era mode uses grouping, return as-is (groupAlbumsByEra handles ordering)
      return albums;
    }

    const sorted = [...albums];
    if (sortBy === 'az') {
      // Alphabetical by title
      sorted.sort((a, b) => (a.title || '').localeCompare(b.title || ''));
    } else if (sortBy === 'year') {
      // Newest first (descending year)
      sorted.sort((a, b) => (b.year || 0) - (a.year || 0));
    }
    return sorted;
  }, [albums, sortBy]);

  // Group albums by era (only used in era mode)
  const eraGroups = useMemo(() => {
    if (sortBy !== 'era') return [];
    return groupAlbumsByEra(albums);
  }, [albums, sortBy]);

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

  // Render content based on sort mode
  const renderContent = () => {
    if (sortBy === 'era') {
      // Era-grouped rendering
      return eraGroups.map((eraGroup) => (
        <EraSection
          key={eraGroup.label}
          label={eraGroup.label}
          albums={eraGroup.albums}
          fingerprints={fingerprints}
          onAlbumClick={onAlbumClick}
          onAlbumHover={onAlbumHover}
          onAlbumHoverEnd={onAlbumHoverEnd}
        />
      ));
    }

    // Flat grid for A-Z and Year modes
    return (
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
          gap: tokens.spacing.lg,
        }}
      >
        {sortedAlbums.map((album) => (
          <AlbumCard
            key={album.id}
            albumId={album.id}
            title={album.title}
            artist={album.artist}
            trackCount={album.trackCount}
            year={album.year}
            hasArtwork={!!album.artworkUrl}
            fingerprint={fingerprints.get(album.id) ?? undefined}
            onClick={() => onAlbumClick?.(album.id)}
            onHoverEnter={() => onAlbumHover?.(album.id, album.title, album.artist)}
            onHoverLeave={() => onAlbumHoverEnd?.()}
          />
        ))}
      </div>
    );
  };

  return (
    <div
      style={{
        height: '100%',
        overflow: 'auto',
        padding: tokens.spacing.group,
      }}
    >
      {renderContent()}

      {/* Sentinel element for infinite scroll */}
      {hasNextPage && (
        <div
          ref={loadMoreRef}
          style={{
            padding: tokens.spacing.group,
            textAlign: 'center',
            minHeight: tokens.spacing.xxl,
          }}
        >
          {isFetchingNextPage ? 'Loading more albums...' : '\u00A0'}
        </div>
      )}
    </div>
  );
};

export default CozyAlbumGrid;
