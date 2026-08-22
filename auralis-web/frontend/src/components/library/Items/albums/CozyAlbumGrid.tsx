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
 *
 * The two rendering strategies (flat-virtualized, era-grouped) live in
 * VirtualizedAlbumGrid.tsx / EraGroupedAlbums.tsx (split out in #4456 to
 * keep this file under the 300-line guideline).
 */

import { useMemo } from 'react';
import { EmptyState } from '@/components/shared/ui/feedback';
import { AlbumGridLoadingState } from './AlbumGridLoadingState';
import { VirtualizedAlbumGrid } from './VirtualizedAlbumGrid';
import { EraGroupedAlbums } from './EraGroupedAlbums';
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
export const CozyAlbumGrid = ({
  onAlbumClick,
  onAlbumHover,
  onAlbumHoverEnd,
  sortBy = 'az',
}: CozyAlbumGridProps) => {
  // Infinite query with TanStack Query
  const {
    data,
    isLoading,
    error,
    fetchNextPage,
    hasNextPage,
  } = useInfiniteAlbums({ limit: 50 });

  // Flatten all pages into single array
  const albums = useMemo(() => data?.pages.flatMap(page => page.albums) ?? [], [data?.pages]);

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
    return groupAlbumsByEra<import('@/types/domain').Album>(albums);
  }, [albums, sortBy]);

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

  // role="list" (not "grid") — this is a flat collection of albums without 2D
  // keyboard navigation; a complete grid→row→gridcell chain isn't needed. Each
  // AlbumCard is wrapped in role="listitem" below (#3962).
  return (
    <div role="list" aria-label="Albums" style={{ padding: tokens.spacing.group }}>
      {sortBy === 'era' ? (
        <EraGroupedAlbums
          eraGroups={eraGroups}
          fingerprints={fingerprints}
          hasNextPage={hasNextPage ?? false}
          onLoadMore={fetchNextPage}
          onAlbumClick={onAlbumClick}
          onAlbumHover={onAlbumHover}
          onAlbumHoverEnd={onAlbumHoverEnd}
        />
      ) : (
        <VirtualizedAlbumGrid
          albums={sortedAlbums}
          fingerprints={fingerprints}
          hasNextPage={hasNextPage ?? false}
          onLoadMore={fetchNextPage}
          onAlbumClick={onAlbumClick}
          onAlbumHover={onAlbumHover}
          onAlbumHoverEnd={onAlbumHoverEnd}
        />
      )}
    </div>
  );
};

export default CozyAlbumGrid;
