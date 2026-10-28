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
 * - Multiple sort modes: A-Z (default), Year, Era-based grouping — all server-ordered
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
import { EmptyState, LoadMoreError } from '@/components/shared/ui/feedback';
import { AlbumGridLoadingState } from './AlbumGridLoadingState';
import { VirtualizedAlbumGrid } from './VirtualizedAlbumGrid';
import { EraGroupedAlbums } from './EraGroupedAlbums';
import {
  useInfiniteAlbums,
  type AlbumOrderBy,
  type SortDirection,
} from '@/hooks/library/useInfiniteAlbums';
import { useAlbumFingerprints } from '@/hooks/fingerprint/useAlbumFingerprint';
import { groupAlbumsByEra } from '@/utils/eraGrouping';
import { tokens } from '@/design-system';

/** Sort options for album grid */
export type AlbumSortOption = 'az' | 'year' | 'era';

/**
 * Each sort mode is a server order (#5868). Re-sorting the loaded pages in the
 * browser showed the newest of the first 50 *alphabetical* albums and moved
 * rows above the viewport as later pages arrived. Era mode groups newest-first,
 * so it streams the year-descending order and only ever extends its last group.
 */
const SERVER_ORDER: Record<AlbumSortOption, { orderBy: AlbumOrderBy; order: SortDirection }> = {
  az: { orderBy: 'title', order: 'asc' },
  year: { orderBy: 'year', order: 'desc' },
  era: { orderBy: 'year', order: 'desc' },
};

interface CozyAlbumGridProps {
  onAlbumClick?: (albumId: number, albumTitle?: string, albumArtist?: string) => void;
  onAlbumHover?: (albumId: number, albumTitle?: string, albumArtist?: string) => void;
  onAlbumHoverEnd?: () => void;
  /** Sort mode: 'az' (alphabetical), 'year' (newest first), 'era' (grouped by era) */
  sortBy?: AlbumSortOption;
  /** Server-side search term (#5866). */
  search?: string;
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
  search,
}: CozyAlbumGridProps) => {
  // Infinite query with TanStack Query
  const {
    data,
    isLoading,
    error,
    fetchNextPage,
    hasNextPage,
    isFetchNextPageError,
    isFetchingNextPage,
    refetch,
  } = useInfiniteAlbums({ limit: 50, search, ...SERVER_ORDER[sortBy] });

  // Flatten all pages into single array
  const albums = useMemo(() => data?.pages.flatMap(page => page.albums) ?? [], [data?.pages]);

  // Extract album IDs for batch fingerprint fetching
  const albumIds = useMemo(() => albums.map(album => album.id), [albums]);

  // Batch fetch fingerprints for all albums
  const { fingerprints } = useAlbumFingerprints(albumIds);

  // Group albums by era (only used in era mode)
  const eraGroups = useMemo(() => {
    if (sortBy !== 'era') return [];
    return groupAlbumsByEra<import('@/types/domain').Album>(albums);
  }, [albums, sortBy]);

  // Loading state
  if (isLoading && albums.length === 0) {
    return <AlbumGridLoadingState />;
  }

  // Error state — only with nothing loaded. TanStack keeps `data` when a
  // later page fails; replacing it threw away the user's rows and scroll
  // position on one transient 503 (#5870), so that case is an inline row.
  if (error && albums.length === 0) {
    return (
      <EmptyState
        role="alert"
        title="Error Loading Albums"
        description={error.message || 'Failed to load albums'}
        actionLabel="Retry"
        onAction={() => void refetch()}
      />
    );
  }

  // Auto-loading pauses while a failed page waits for Retry.
  const canLoadMore = (hasNextPage ?? false) && !isFetchNextPageError;

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
    <>
      <div role="list" aria-label="Albums" style={{ padding: tokens.spacing.group }}>
        {sortBy === 'era' ? (
          <EraGroupedAlbums
            eraGroups={eraGroups}
            fingerprints={fingerprints}
            hasNextPage={canLoadMore}
            onLoadMore={fetchNextPage}
            onAlbumClick={onAlbumClick}
            onAlbumHover={onAlbumHover}
            onAlbumHoverEnd={onAlbumHoverEnd}
          />
        ) : (
          <VirtualizedAlbumGrid
            albums={albums}
            fingerprints={fingerprints}
            hasNextPage={canLoadMore}
            onLoadMore={fetchNextPage}
            onAlbumClick={onAlbumClick}
            onAlbumHover={onAlbumHover}
            onAlbumHoverEnd={onAlbumHoverEnd}
          />
        )}
      </div>
      {/* Outside role="list", whose children must be list items. */}
      {isFetchNextPageError && !isFetchingNextPage && (
        <LoadMoreError noun="albums" onRetry={() => void fetchNextPage()} />
      )}
    </>
  );
};

export default CozyAlbumGrid;
