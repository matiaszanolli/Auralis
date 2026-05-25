/**
 * AlbumGridContent Component
 *
 * Renders the grid of album cards.
 *
 * #3606: virtualized via `useGridVirtualizer` — only the rows currently in or
 * near the viewport mount, so DOM `AlbumCard` count scales with the viewport
 * rather than the loaded dataset. Falls back to mapping every album when the
 * scroll element / container width are unmeasurable (jsdom tests).
 */

import { RefObject, useEffect, useState } from 'react';
import { tokens } from '@/design-system';
import { AlbumCard } from '@/components/album/AlbumCard/AlbumCard';
import { GridContainer } from '@/components/library/Styles/Grid.styles';
import InfiniteScrollTrigger from '@/components/library/Items/utilities/InfiniteScrollTrigger';
import EndOfListIndicator from '@/components/library/Items/utilities/EndOfListIndicator';
import GridLoadingState from '@/components/library/Items/utilities/GridLoadingState';
import {
  computeColumnsPerRow,
  useContainerWidth,
  useGridVirtualizer,
} from '@/components/library/Items/utilities/useGridVirtualizer';

// Card ~216px square + title/artist line + row gap.
const ROW_HEIGHT = 320;
const MIN_COLUMN_WIDTH = 216;
const GAP_PX = 24; // tokens.spacing.lg as px

interface Album {
  id: number;
  title: string;
  artist: string;
  track_count: number;
  total_duration: number;
  year?: number;
  artwork_url?: string;
}

interface AlbumGridContentProps {
  albums: Album[];
  hasMore: boolean;
  isLoadingMore: boolean;
  totalAlbums: number;
  containerRef: RefObject<HTMLDivElement>;
  loadMoreTriggerRef: RefObject<HTMLDivElement>;
  onAlbumClick: (albumId: number) => void;
}

export const AlbumGridContent = ({
  albums,
  hasMore,
  isLoadingMore,
  totalAlbums,
  containerRef,
  loadMoreTriggerRef,
  onAlbumClick,
}: AlbumGridContentProps) => {
  const [scrollElement, setScrollElement] = useState<HTMLElement | null>(null);

  useEffect(() => {
    // GridContainer is itself the scroll element when used as a fixed-height
    // panel; fall back to the page-level scroll container otherwise.
    const container = containerRef.current;
    if (container && container.scrollHeight > container.clientHeight) {
      setScrollElement(container);
    } else {
      setScrollElement(document.getElementById('app-main-content-scroll'));
    }
  }, [containerRef]);

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
    /* #3603: pass the parent's onAlbumClick directly (it accepts an albumId).
        AlbumCard binds the click handler internally so we avoid creating a new
        inline arrow per render — preserves AlbumCard's React.memo across
        re-renders of the parent. */
    <AlbumCard
      key={album.id}
      albumId={album.id}
      title={album.title}
      artist={album.artist}
      trackCount={album.track_count}
      duration={album.total_duration}
      year={album.year}
      hasArtwork={!!album.artwork_url}
      onClick={onAlbumClick}
    />
  );

  return (
    <GridContainer ref={containerRef}>
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
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: `repeat(auto-fill, minmax(${MIN_COLUMN_WIDTH}px, 1fr))`,
            gap: tokens.spacing.lg,
          }}
        >
          {albums.map(renderCard)}
        </div>
      )}

      {hasMore && <InfiniteScrollTrigger ref={loadMoreTriggerRef} />}
      {isLoadingMore && (
        <GridLoadingState current={albums.length} total={totalAlbums} itemType="albums" />
      )}
      {!hasMore && albums.length > 0 && (
        <EndOfListIndicator count={totalAlbums} itemType="albums" />
      )}
    </GridContainer>
  );
};
