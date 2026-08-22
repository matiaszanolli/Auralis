/**
 * Virtualized flat-mode album grid, extracted from CozyAlbumGrid.tsx (#4456).
 *
 * Renders only the rows currently in (or near) the viewport via
 * `useGridVirtualizer`, then drives infinite-scroll loading by watching the
 * index of the last visible virtual row. In test environments where the
 * scroll element / container width are unavailable, the renderer falls back
 * to mapping every album so DOM-presence assertions keep working.
 */

import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { AlbumCard } from '@/components/album/AlbumCard/AlbumCard';
import { tokens } from '@/design-system';
import {
  computeColumnsPerRow,
  useContainerWidth,
  useGridVirtualizer,
} from '@/components/library/Items/utilities/useGridVirtualizer';
import type { VirtualizedGridSharedProps } from './albumGridTypes';

// Card visual height (~180px square) + room for title/artist + row gap.
const COZY_ROW_HEIGHT = 284;
const COZY_MIN_COLUMN = 180;
const COZY_GAP_PX = 24; // tokens.spacing.lg as px

interface VirtualizedAlbumGridProps extends VirtualizedGridSharedProps {
  albums: import('@/types/domain').Album[];
}

export function VirtualizedAlbumGrid({
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

  // #5120: a layout effect, not a passive one. `useEffect` runs *after* paint,
  // so the first committed frame took the `canVirtualize === false` branch and
  // painted every item unwindowed before swapping to the structurally different
  // virtualized tree — a visible flash plus a full mount/unmount of every row on
  // each navigation. `useContainerWidth` already resolves pre-paint the same way.
  useLayoutEffect(() => {
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
