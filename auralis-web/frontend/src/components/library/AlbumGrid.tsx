/**
 * AlbumGrid Component
 * ~~~~~~~~~~~~~~~~~~~
 *
 * Grid layout for displaying albums using AlbumCard components.
 * Handles pagination and responsive columns.
 *
 * Usage:
 * ```typescript
 * <AlbumGrid />
 * ```
 *
 * @module components/library/AlbumGrid
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { tokens } from '@/design-system';
import { useAlbumsQuery } from '@/hooks/library/useLibraryQuery';
import { AlbumCard } from '@/components/album/AlbumCard/AlbumCard';
import type { Album } from '@/types/domain';
import {
  computeColumnsPerRow,
  useContainerWidth,
  useGridVirtualizer,
} from '@/components/library/Items/utilities/useGridVirtualizer';

// Card ~216px square + title/artist line + row gap.
const ROW_HEIGHT = 320;
const MIN_COLUMN_WIDTH = 216;
const GAP_PX = 24;

interface AlbumGridProps {
  /** Callback when album is selected */
  onAlbumSelect?: (album: Album) => void;

  /** Number of albums per page */
  limit?: number;
}

/**
 * AlbumGrid component
 *
 * Responsive grid of album cards with infinite scroll.
 * Adapts column count based on viewport width.
 */
export const AlbumGrid = ({
  onAlbumSelect,
  limit = 20,
}: AlbumGridProps) => {
  const { data: albums, isLoading, error, hasMore, fetchMore } = useAlbumsQuery({ limit });

  const handleAlbumSelect = useCallback(
    (album: Album) => {
      onAlbumSelect?.(album);
    },
    [onAlbumSelect]
  );

  // #3603: stable id→Album lookup so the per-card onClick is a stable callback
  // (preserves AlbumCard's React.memo across parent re-renders).
  const albumById = useMemo(() => {
    const map = new Map<number, Album>();
    for (const a of albums) map.set(a.id, a);
    return map;
  }, [albums]);

  const handleAlbumCardClick = useCallback(
    (albumId: number) => {
      const album = albumById.get(albumId);
      if (album) handleAlbumSelect(album);
    },
    [albumById, handleAlbumSelect]
  );

  if (error) {
    return (
      <section style={styles.errorContainer} role="alert" aria-live="assertive">
        <p>Failed to load albums</p>
        <p style={styles.errorSubtext}>{error.message}</p>
      </section>
    );
  }

  if (albums.length === 0 && !isLoading) {
    return (
      <section style={styles.emptyContainer} role="status" aria-live="polite">
        <p>No albums found</p>
      </section>
    );
  }

  return (
    <section style={styles.container} aria-label="Albums library">
      <VirtualizedAlbumList
        albums={albums}
        onAlbumClick={handleAlbumCardClick}
      />

      {isLoading && (
        <div style={styles.loadingMessage} role="status" aria-live="polite" aria-atomic="true">
          Loading more albums...
        </div>
      )}

      {!hasMore && albums.length > 0 && (
        <div style={styles.endMessage} role="status" aria-live="polite">
          End of list
        </div>
      )}

      {hasMore && (
        <button
          onClick={fetchMore}
          disabled={isLoading}
          style={styles.loadMoreButton}
          aria-label={`Load more albums (${albums.length} loaded)`}
        >
          {isLoading ? 'Loading...' : 'Load More'}
        </button>
      )}
    </section>
  );
};

interface VirtualizedAlbumListProps {
  albums: Album[];
  onAlbumClick: (albumId: number) => void;
}

/**
 * #3606: virtualized album list. Renders only visible rows + overscan via
 * `useGridVirtualizer`; falls back to mapping every album when layout is
 * unmeasurable (jsdom tests).
 */
function VirtualizedAlbumList({ albums, onAlbumClick }: VirtualizedAlbumListProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [scrollElement, setScrollElement] = useState<HTMLElement | null>(null);

  useEffect(() => {
    setScrollElement(document.getElementById('app-main-content-scroll'));
  }, []);

  const containerWidth = useContainerWidth(containerRef);
  const columns = computeColumnsPerRow(containerWidth, MIN_COLUMN_WIDTH, GAP_PX);

  const virtualizer = useGridVirtualizer({
    itemCount: albums.length,
    columnsPerRow: columns,
    rowHeight: ROW_HEIGHT,
    getScrollElement: () => scrollElement,
    scrollMargin: containerRef.current?.offsetTop ?? 0,
  });

  const canVirtualize = scrollElement !== null && containerWidth > 0;
  const virtualRows = virtualizer.getVirtualItems();

  const renderCard = (album: Album) => (
    <div key={album.id} role="listitem">
      <AlbumCard
        albumId={album.id}
        title={album.title}
        artist={album.artist}
        trackCount={album.trackCount}
        hasArtwork={!!album.artworkUrl}
        year={album.year}
        onClick={onAlbumClick}
      />
    </div>
  );

  return (
    <div ref={containerRef} role="list">
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
                {rowAlbums.map(renderCard)}
              </div>
            );
          })}
        </div>
      ) : (
        <div style={styles.grid}>{albums.map(renderCard)}</div>
      )}
    </div>
  );
}

const styles = {
  container: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: tokens.spacing.lg,
    width: '100%',
    padding: `0 ${tokens.spacing.lg}`,
  },

  grid: {
    display: 'grid',
    // Responsive columns: 2 (mobile) → 3 (tablet) → 4 (desktop) → 5-6 (ultra)
    // Album cards: 200×200px per spec (tokens.components.albumCard.size)
    gridTemplateColumns: 'repeat(auto-fill, minmax(216px, 1fr))',
    gap: tokens.spacing.lg,
    width: '100%',

    // Mobile: 2 columns
    [`@media (max-width: ${tokens.breakpoints.sm})`]: {
      gridTemplateColumns: 'repeat(2, 1fr)',
      gap: tokens.spacing.md,
      padding: `0 ${tokens.spacing.sm}`,
    },

    // Tablet: 3 columns
    [`@media (min-width: ${tokens.breakpoints.sm}) and (max-width: ${tokens.breakpoints.md})`]: {
      gridTemplateColumns: 'repeat(3, 1fr)',
      gap: tokens.spacing.md,
    },

    // Desktop: 4 columns
    [`@media (min-width: ${tokens.breakpoints.md}) and (max-width: ${tokens.breakpoints.lg})`]: {
      gridTemplateColumns: 'repeat(4, 1fr)',
      gap: tokens.spacing.lg,
    },

    // Ultra-wide: 5+ columns
    [`@media (min-width: ${tokens.breakpoints.lg})`]: {
      gridTemplateColumns: 'repeat(auto-fill, minmax(216px, 1fr))',
      gap: tokens.spacing.lg,
    },
  },

  errorContainer: {
    padding: tokens.spacing.lg,
    backgroundColor: tokens.colors.semantic.error,
    color: tokens.colors.text.primary,
    borderRadius: tokens.borderRadius.lg,
    textAlign: 'center' as const,
  },

  errorSubtext: {
    fontSize: tokens.typography.fontSize.sm,
    opacity: 0.8,
    marginTop: tokens.spacing.sm,
  },

  emptyContainer: {
    padding: tokens.spacing.xl,
    textAlign: 'center' as const,
    color: tokens.colors.text.tertiary,
    borderRadius: tokens.borderRadius.lg,
    backgroundColor: tokens.colors.bg.level2,
  },

  loadingMessage: {
    textAlign: 'center' as const,
    color: tokens.colors.text.secondary,
    padding: tokens.spacing.md,
    fontSize: tokens.typography.fontSize.sm,
  },

  endMessage: {
    textAlign: 'center' as const,
    color: tokens.colors.text.tertiary,
    padding: tokens.spacing.md,
    fontSize: tokens.typography.fontSize.sm,
  },

  loadMoreButton: {
    alignSelf: 'center' as const,
    padding: `${tokens.spacing.sm} ${tokens.spacing.lg}`,
    background: tokens.gradients.aurora,
    color: tokens.colors.text.primary,
    border: 'none',
    borderRadius: tokens.borderRadius.md,
    cursor: 'pointer',
    fontSize: tokens.typography.fontSize.md,
    fontWeight: tokens.typography.fontWeight.semibold,
    transition: tokens.transitions.all,
    boxShadow: tokens.shadows.md,
    outline: 'none',

    ':hover': {
      boxShadow: tokens.shadows.glowMd,
      transform: 'scale(1.02)',              // Scale-based hover (Design Language §5)
    },

    ':active': {
      transform: 'scale(0.98)',              // Press inward for tactile feedback
    },

    ':disabled': {
      opacity: 0.5,
      cursor: 'not-allowed',
    },
  },
};

export default AlbumGrid;
