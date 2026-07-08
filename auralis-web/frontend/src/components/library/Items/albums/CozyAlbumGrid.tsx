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

import { useEffect, useMemo, useRef, useState } from 'react';
import { EmptyState } from '@/components/shared/ui/feedback';
import { AlbumGridLoadingState } from './AlbumGridLoadingState';
import { EraSection } from './EraSection';
import { AlbumCard } from '@/components/album/AlbumCard/AlbumCard';
import { useInfiniteAlbums } from '@/hooks/library/useInfiniteAlbums';
import { useAlbumFingerprints } from '@/hooks/fingerprint/useAlbumFingerprint';
import { groupAlbumsByEra } from '@/utils/eraGrouping';
import { tokens } from '@/design-system';
import {
  computeColumnsPerRow,
  useContainerWidth,
  useGridVirtualizer,
} from '@/components/library/Items/utilities/useGridVirtualizer';

// Card visual height (~180px square) + room for title/artist + row gap.
const COZY_ROW_HEIGHT = 284;
const COZY_MIN_COLUMN = 180;
const COZY_GAP_PX = 24; // tokens.spacing.lg as px

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

interface VirtualizedGridSharedProps {
  fingerprints: Map<number, import('@/utils/fingerprintToGradient').AudioFingerprint | null>;
  hasNextPage: boolean;
  onLoadMore: () => void;
  onAlbumClick?: (albumId: number) => void;
  onAlbumHover?: (albumId: number, albumTitle?: string, albumArtist?: string) => void;
  onAlbumHoverEnd?: () => void;
}

interface VirtualizedAlbumGridProps extends VirtualizedGridSharedProps {
  albums: import('@/types/domain').Album[];
}

/**
 * Virtualized flat-mode album grid.
 *
 * Renders only the rows currently in (or near) the viewport via
 * `useGridVirtualizer`, then drives infinite-scroll loading by watching the
 * index of the last visible virtual row. In test environments where the
 * scroll element / container width are unavailable, the renderer falls back
 * to mapping every album so DOM-presence assertions keep working.
 */
function VirtualizedAlbumGrid({
  albums,
  fingerprints,
  hasNextPage,
  onLoadMore,
  onAlbumClick,
  onAlbumHover,
  onAlbumHoverEnd,
}: VirtualizedAlbumGridProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const scrollElementRef = useRef<HTMLElement | null>(null);
  const [scrollReady, setScrollReady] = useState(false);

  useEffect(() => {
    scrollElementRef.current = document.getElementById('app-main-content-scroll');
    setScrollReady(scrollElementRef.current !== null);
  }, []);

  const containerWidth = useContainerWidth(containerRef);
  const columns = computeColumnsPerRow(containerWidth, COZY_MIN_COLUMN, COZY_GAP_PX);

  const virtualizer = useGridVirtualizer({
    itemCount: albums.length,
    columnsPerRow: columns,
    rowHeight: COZY_ROW_HEIGHT,
    getScrollElement: () => scrollElementRef.current,
    scrollMargin: containerRef.current?.offsetTop ?? 0,
  });

  // Near-end load: when the last rendered virtual row is within one viewport
  // of the dataset end, request the next page. Matches the TrackListView
  // pattern (TrackListViewContent.tsx) so behaviour stays consistent.
  const virtualRows = virtualizer.getVirtualItems();
  const lastRow = virtualRows[virtualRows.length - 1];
  useEffect(() => {
    if (!hasNextPage || !lastRow) return;
    const remainingRows = Math.max(0, Math.ceil(albums.length / Math.max(1, columns)) - lastRow.index);
    if (remainingRows <= 2) onLoadMore();
  }, [lastRow?.index, albums.length, columns, hasNextPage, onLoadMore]);

  // Fallback mode needs its own IntersectionObserver-driven sentinel — the
  // virtualizer's near-end-row detector does not run when canVirtualize=false.
  const fallbackSentinelRef = useRef<HTMLDivElement>(null);
  const canVirtualize = scrollReady && containerWidth > 0;

  useEffect(() => {
    if (canVirtualize) return;
    const target = fallbackSentinelRef.current;
    if (!target || !hasNextPage) return;
    if (typeof IntersectionObserver === 'undefined') return;
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) onLoadMore();
        }
      },
      { rootMargin: '400px' }
    );
    observer.observe(target);
    return () => observer.disconnect();
  }, [canVirtualize, hasNextPage, onLoadMore]);

  return (
    <div ref={containerRef}>
      {canVirtualize ? (
        <div
          style={{
            height: virtualizer.getTotalSize(),
            width: '100%',
            position: 'relative',
          }}
        >
          {virtualRows.map((virtualRow) => {
            const startIndex = virtualRow.index * columns;
            const rowAlbums = albums.slice(startIndex, startIndex + columns);
            return (
              <div
                key={virtualRow.index}
                style={{
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  width: '100%',
                  transform: `translateY(${virtualRow.start - (virtualizer.options.scrollMargin ?? 0)}px)`,
                  display: 'grid',
                  gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))`,
                  gap: tokens.spacing.lg,
                }}
              >
                {rowAlbums.map((album) => (
                  <div role="listitem" key={album.id}>
                    <AlbumCard
                      albumId={album.id}
                      title={album.title}
                      artist={album.artist}
                      trackCount={album.trackCount}
                      year={album.year}
                      hasArtwork={!!album.artworkUrl}
                      fingerprint={fingerprints.get(album.id) ?? undefined}
                      onClick={onAlbumClick}
                      onHoverEnter={onAlbumHover}
                      onHoverLeave={onAlbumHoverEnd}
                    />
                  </div>
                ))}
              </div>
            );
          })}
        </div>
      ) : (
        // Fallback for environments without measurable layout (jsdom tests):
        // render every album so getByTestId() assertions still resolve.
        <>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: `repeat(auto-fill, minmax(${COZY_MIN_COLUMN}px, 1fr))`,
              gap: tokens.spacing.lg,
            }}
          >
            {albums.map((album) => (
              <div role="listitem" key={album.id}>
                <AlbumCard
                  albumId={album.id}
                  title={album.title}
                  artist={album.artist}
                  trackCount={album.trackCount}
                  year={album.year}
                  hasArtwork={!!album.artworkUrl}
                  fingerprint={fingerprints.get(album.id) ?? undefined}
                  onClick={onAlbumClick}
                  onHoverEnter={onAlbumHover}
                  onHoverLeave={onAlbumHoverEnd}
                />
              </div>
            ))}
          </div>
          {hasNextPage && (
            <div ref={fallbackSentinelRef} style={{ height: 1 }} aria-hidden="true" />
          )}
        </>
      )}
    </div>
  );
}

interface EraGroupedAlbumsProps extends VirtualizedGridSharedProps {
  eraGroups: ReturnType<typeof groupAlbumsByEra<import('@/types/domain').Album>>;
}

/**
 * Era-mode rendering: lists `EraSection`s (each internally virtualized) and
 * drives infinite-scroll loading from a sentinel at the bottom of the list.
 */
function EraGroupedAlbums({
  eraGroups,
  fingerprints,
  hasNextPage,
  onLoadMore,
  onAlbumClick,
  onAlbumHover,
  onAlbumHoverEnd,
}: EraGroupedAlbumsProps) {
  const sentinelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const target = sentinelRef.current;
    if (!target || !hasNextPage) return;
    if (typeof IntersectionObserver === 'undefined') return;
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) onLoadMore();
        }
      },
      { rootMargin: '400px' }
    );
    observer.observe(target);
    return () => observer.disconnect();
  }, [hasNextPage, onLoadMore]);

  return (
    <>
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
      {hasNextPage && (
        <div
          ref={sentinelRef}
          style={{ padding: tokens.spacing.group, textAlign: 'center' }}
        >
          Loading more albums...
        </div>
      )}
    </>
  );
}

export default CozyAlbumGrid;
