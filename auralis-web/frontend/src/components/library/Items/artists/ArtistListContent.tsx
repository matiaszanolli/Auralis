import { MouseEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Typography } from '@mui/material';
import { useVirtualizer } from '@tanstack/react-virtual';
import { ContextMenu, ContextMenuAction } from '@/components/shared/ContextMenu';
import { ArtistListLoadingIndicator } from './ArtistListLoadingIndicator';
import { ArtistListHeader } from './ArtistListHeader';
import { ArtistListItem } from './ArtistListItem';
import { AlphabetDivider } from '@/components/library/Styles/ArtistList.styles';
import {
  ArtistListContainer,
  EndOfListIndicator,
} from './CozyArtistList.styles';
import type { Artist } from '@/types/domain';

/**
 * Use domain Artist type (camelCase: albumCount, trackCount)
 * instead of local snake_case interface
 */
type ArtistItem = Artist;

interface ArtistContextMenuState {
  isOpen: boolean;
  mousePosition?: { top: number; left: number };
}

interface ArtistListContentProps {
  artists: ArtistItem[];
  totalArtists: number;
  isLoadingMore: boolean;
  hasMore: boolean;
  fetchMore: () => Promise<void>;
  groupedArtists: Record<string, ArtistItem[]>;
  sortedLetters: string[];
  contextMenuState: ArtistContextMenuState;
  contextActions: ContextMenuAction[];
  onArtistClick: (artist: ArtistItem) => void;
  onContextMenuOpen: (artist: ArtistItem, event: MouseEvent) => void;
  onContextMenuClose: () => void;
}

/** A single flattened virtual row: either an alphabet header or an artist. */
type FlatRow =
  | { kind: 'header'; key: string; letter: string }
  | { kind: 'artist'; key: string; artist: ArtistItem };

// Estimated row heights for the variable-height virtualizer. measureElement
// refines these to the real rendered heights, so they only seed the layout.
const HEADER_HEIGHT = 72; // AlphabetDivider (marginTop xxl + line + marginBottom md)
const ROW_HEIGHT = 84; // ArtistListItem button (minHeight 64) + StyledListItem margin

/**
 * ArtistListContent - Renders the artist list with DOM windowing (#3957).
 *
 * The alphabet headers and artist rows are flattened into a single list and
 * rendered through `useVirtualizer` against the shared `#app-main-content-scroll`
 * element (the same external-scroll + scrollMargin pattern the album views use),
 * so the rendered DOM stays bounded on large libraries instead of appending
 * every section like the previous InfiniteScroll + per-section map() did.
 * Infinite loading is driven off the last rendered virtual row.
 *
 * In environments without measurable layout (jsdom) the virtualizer can't run,
 * so it falls back to rendering every row — preserving correctness in tests.
 */
export const ArtistListContent = ({
  artists,
  totalArtists,
  isLoadingMore,
  hasMore,
  fetchMore,
  groupedArtists,
  sortedLetters,
  contextMenuState,
  contextActions,
  onArtistClick,
  onContextMenuOpen,
  onContextMenuClose,
}: ArtistListContentProps) => {
  // #3607: stable callback identity so ArtistListItem doesn't re-render needlessly.
  const handleContextMenu = useCallback(
    (e: MouseEvent, artist: ArtistItem) => onContextMenuOpen(artist, e),
    [onContextMenuOpen]
  );

  // Flatten the alphabetical groups into one list of header + artist rows.
  const rows = useMemo<FlatRow[]>(() => {
    const flat: FlatRow[] = [];
    for (const letter of sortedLetters) {
      flat.push({ kind: 'header', key: `header-${letter}`, letter });
      for (const artist of groupedArtists[letter] ?? []) {
        flat.push({ kind: 'artist', key: `artist-${artist.id}`, artist });
      }
    }
    return flat;
  }, [sortedLetters, groupedArtists]);

  // Virtualize against the shared scroll container (external scroll pattern).
  const containerRef = useRef<HTMLDivElement>(null);
  const scrollElementRef = useRef<HTMLElement | null>(null);
  const [scrollReady, setScrollReady] = useState(false);

  useEffect(() => {
    scrollElementRef.current = document.getElementById('app-main-content-scroll');
    setScrollReady(scrollElementRef.current !== null);
  }, []);

  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => scrollElementRef.current,
    estimateSize: (index) =>
      rows[index]?.kind === 'header' ? HEADER_HEIGHT : ROW_HEIGHT,
    overscan: 8,
    scrollMargin: containerRef.current?.offsetTop ?? 0,
    getItemKey: (index) => rows[index]?.key ?? index,
  });

  const virtualRows = virtualizer.getVirtualItems();

  // Infinite scroll: fetch the next page once the last row is rendered
  // (mirrors the album/track virtualized lists).
  useEffect(() => {
    const last = virtualRows[virtualRows.length - 1];
    if (!last) return;
    if (last.index >= rows.length - 1 && hasMore && !isLoadingMore) {
      fetchMore().catch((err) =>
        console.error('Failed to fetch more artists:', err)
      );
    }
  }, [virtualRows, rows.length, hasMore, isLoadingMore, fetchMore]);

  const renderRow = (row: FlatRow) =>
    row.kind === 'header' ? (
      <AlphabetDivider>{row.letter}</AlphabetDivider>
    ) : (
      <ArtistListItem
        artist={row.artist}
        onClick={onArtistClick}
        onContextMenu={handleContextMenu}
      />
    );

  // jsdom / unmeasurable layout: virtualizer can't position rows — render all.
  const canVirtualize = scrollReady;

  return (
    <ArtistListContainer>
      <ArtistListHeader loadedCount={artists.length} totalCount={totalArtists} />

      <div ref={containerRef}>
        {canVirtualize ? (
          <div
            style={{
              height: virtualizer.getTotalSize(),
              width: '100%',
              position: 'relative',
            }}
          >
            {virtualRows.map((virtualRow) => (
              <div
                key={virtualRow.key}
                data-index={virtualRow.index}
                ref={virtualizer.measureElement}
                style={{
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  width: '100%',
                  transform: `translateY(${virtualRow.start - (virtualizer.options.scrollMargin ?? 0)}px)`,
                }}
              >
                {renderRow(rows[virtualRow.index])}
              </div>
            ))}
          </div>
        ) : (
          <div>
            {rows.map((row) => (
              <div key={row.key}>{renderRow(row)}</div>
            ))}
          </div>
        )}
      </div>

      {isLoadingMore && (
        <ArtistListLoadingIndicator
          currentCount={artists.length}
          totalCount={totalArtists}
        />
      )}

      {artists.length > 0 && !hasMore && (
        <EndOfListIndicator>
          <Typography variant="body2" sx={{ color: 'text.secondary' }}>
            Showing all {totalArtists} artists
          </Typography>
        </EndOfListIndicator>
      )}

      {/* Context menu */}
      <ContextMenu
        anchorPosition={contextMenuState.mousePosition}
        open={contextMenuState.isOpen}
        onClose={onContextMenuClose}
        actions={contextActions}
      />
    </ArtistListContainer>
  );
};

export default ArtistListContent;
