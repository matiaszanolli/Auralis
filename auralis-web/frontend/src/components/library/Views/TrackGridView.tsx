import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { tokens } from '@/design-system';
import { TrackCard } from '@/components/track/TrackCard';
import {
  computeColumnsPerRow,
  useContainerWidth,
  useGridVirtualizer,
} from '@/components/library/Items/utilities/useGridVirtualizer';
import type { LibraryTrack as Track } from '@/types/domain';

// Matches AlbumGridContent's MediaCard-based sizing (TrackCard is a thin
// MediaCard wrapper, so the same footprint applies).
const ROW_HEIGHT = 320;
const MIN_COLUMN_WIDTH = 216;
const GAP_PX = 24; // tokens.spacing.lg as px

// Hoisted so the per-card wrapper never receives a new style object identity
// on every parent render — an inline `sx` computed per-index previously
// defeated TrackCard's React.memo on every re-render regardless of whether
// that card's own props changed (fixes #3928).
const ENTRY_ANIMATION_STYLES: Array<{ animationDelay: string; animationFillMode: 'both' }> =
  Array.from({ length: 10 }, (_, index) => ({
    animationDelay: `${index * 0.05}s`,
    animationFillMode: 'both',
  }));

export interface TrackGridViewProps {
  tracks: Track[];
  hasMore: boolean;
  currentTrackId?: number;
  onTrackPlay: (track: Track) => void;
  onRemoveTrack: (index: number) => Promise<void>;
  onReorderQueue: (newOrder: number[]) => Promise<void>;
  onShuffleQueue: () => Promise<void>;
  onClearQueue: () => Promise<void>;
}

/**
 * TrackGridView - Virtualized grid layout for track cards
 *
 * Displays tracks as cards with album art and queue management. Row-based
 * virtualization via `useGridVirtualizer` (fixes #3928) bounds DOM
 * `TrackCard` count to roughly the viewport regardless of library size,
 * matching the pattern already used by AlbumGridContent/CozyAlbumGrid.
 * Falls back to rendering every track when the scroll element / container
 * width are unmeasurable (jsdom tests). Infinite-scroll *triggering* is
 * still handled by the parent (TrackListView) via
 * react-infinite-scroll-component — this component only owns rendering.
 *
 * #3576: An id→Track index is built once per `tracks` change so the per-card
 * onPlay callback can be a stable, O(1) lookup `useCallback` instead of an
 * inline arrow doing `tracks.find(...)` per click. The stable identity also
 * preserves `TrackCard`'s `React.memo` across renders.
 */
export const TrackGridView = ({
  tracks,
  currentTrackId: _currentTrackId,
  onTrackPlay,
  onRemoveTrack: _onRemoveTrack,
  onReorderQueue: _onReorderQueue,
  onShuffleQueue: _onShuffleQueue,
  onClearQueue: _onClearQueue,
}: TrackGridViewProps) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [scrollElement, setScrollElement] = useState<HTMLElement | null>(null);

  useEffect(() => {
    // Grid view is wrapped by the parent's <InfiniteScroll scrollableTarget=
    // "app-main-content-scroll">, so that's always the real scroll container.
    setScrollElement(document.getElementById('app-main-content-scroll'));
  }, []);

  const containerWidth = useContainerWidth(containerRef);
  const columns = computeColumnsPerRow(containerWidth, MIN_COLUMN_WIDTH, GAP_PX);

  const virtualizer = useGridVirtualizer({
    itemCount: tracks.length,
    columnsPerRow: columns,
    rowHeight: ROW_HEIGHT,
    getScrollElement: () => scrollElement,
    scrollMargin: containerRef.current?.offsetTop ?? 0,
  });

  const canVirtualize = scrollElement !== null && containerWidth > 0;
  const virtualRows = virtualizer.getVirtualItems();

  const trackById = useMemo(() => {
    const map = new Map<number, Track>();
    for (const track of tracks) map.set(track.id, track);
    return map;
  }, [tracks]);

  const handlePlay = useCallback(
    (id: number) => {
      const found = trackById.get(id);
      if (found) onTrackPlay(found);
    },
    [trackById, onTrackPlay]
  );

  const renderCard = (track: Track, index: number) => (
    <div
      key={track.id}
      className="animate-fade-in-up"
      style={index < ENTRY_ANIMATION_STYLES.length ? ENTRY_ANIMATION_STYLES[index] : undefined}
    >
      <TrackCard
        id={track.id}
        title={track.title}
        artist={track.artist}
        album={track.album}
        albumId={track.albumId ?? undefined}
        duration={track.duration}
        albumArt={track.artworkUrl ?? undefined}
        onPlay={handlePlay}
      />
    </div>
  );

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
            const rowTracks = tracks.slice(startIndex, startIndex + columns);
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
                {rowTracks.map((track, i) => renderCard(track, startIndex + i))}
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
          {tracks.map((track, index) => renderCard(track, index))}
        </div>
      )}
    </div>
  );
};

export default TrackGridView;
