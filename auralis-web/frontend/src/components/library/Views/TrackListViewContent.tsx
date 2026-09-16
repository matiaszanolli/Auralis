import { FocusEvent, KeyboardEvent, MouseEvent, useCallback, useEffect, useRef, useState } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import SelectableTrackRow from '@/components/library/Items/tracks/SelectableTrackRow';
import GridLoadingState from '@/components/library/Items/utilities/GridLoadingState';
import EndOfListIndicator from '@/components/library/Items/utilities/EndOfListIndicator';
import { ListViewContainer } from './TrackListView.styles';
import type { LibraryTrack as Track } from '@/types/domain';

const ROW_HEIGHT = 56; // 44px row + 4px margin + 8px selectable padding

export interface TrackListViewContentProps {
  tracks: Track[];
  hasMore: boolean;
  isLoadingMore: boolean;
  totalTracks: number;
  currentTrackId?: number;
  isPlaying: boolean;
  selectedTracks: Set<number>;
  isSelected: (trackId: number) => boolean;
  onToggleSelect: (trackId: number, e: MouseEvent) => void;
  onTrackPlay: (track: Track) => void;
  onPause: () => void;
  onEditMetadata: (trackId: number) => void;
  onFindSimilar?: (trackId: number) => void;
  onLoadMore?: () => void;
}

/**
 * TrackListViewContent - Virtualized list layout for track rows
 *
 * Uses @tanstack/react-virtual to only render visible tracks (+ overscan buffer),
 * keeping DOM node count constant regardless of library size.
 */
export const TrackListViewContent = ({
  tracks,
  hasMore,
  isLoadingMore,
  totalTracks,
  currentTrackId,
  isPlaying,
  isSelected,
  onToggleSelect,
  onTrackPlay,
  onPause,
  onEditMetadata,
  onFindSimilar,
  onLoadMore,
}: TrackListViewContentProps) => {
  const scrollElementRef = useRef<HTMLElement | null>(null);
  const listContainerRef = useRef<HTMLDivElement>(null);

  // Roving tabindex (#5011, WAI-ARIA APG listbox pattern): exactly one row
  // is tabIndex=0 at a time, so Tab enters/exits the list in one stop while
  // ArrowUp/ArrowDown/Home/End move focus between options instead of every
  // row being independently tabbable.
  const [activeIndex, setActiveIndex] = useState(0);

  // Stable callback refs to avoid recreating row callbacks on every render
  const tracksRef = useRef(tracks);
  tracksRef.current = tracks;
  const onTrackPlayRef = useRef(onTrackPlay);
  onTrackPlayRef.current = onTrackPlay;

  const handlePlay = useCallback((trackId: number) => {
    const foundTrack = tracksRef.current.find((t) => t.id === trackId);
    if (foundTrack) onTrackPlayRef.current(foundTrack);
  }, []);

  // Attach to the app-level scroll container
  useEffect(() => {
    scrollElementRef.current = document.getElementById('app-main-content-scroll');
  }, []);

  const virtualizer = useVirtualizer({
    count: tracks.length,
    getScrollElement: () => scrollElementRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 10,
    scrollMargin: listContainerRef.current?.offsetTop ?? 0,
  });

  // Trigger infinite scroll when near the end of the list
  const virtualItems = virtualizer.getVirtualItems();
  const lastItem = virtualItems[virtualItems.length - 1];

  useEffect(() => {
    if (!lastItem) return;
    if (
      lastItem.index >= tracks.length - 10 &&
      hasMore &&
      !isLoadingMore &&
      onLoadMore
    ) {
      onLoadMore();
    }
  }, [lastItem?.index, tracks.length, hasMore, isLoadingMore, onLoadMore]);

  // Clamp when the list shrinks (filtering, deletion) so the roving stop
  // never points past the end.
  useEffect(() => {
    if (tracks.length === 0) return;
    setActiveIndex((current) => Math.min(current, tracks.length - 1));
  }, [tracks.length]);

  // Move actual DOM focus to the new active row once it exists, but only
  // when a keyboard-navigation action requested it -- not on mount or when
  // the clamp effect above adjusts activeIndex after the list shrinks,
  // neither of which should steal focus from wherever the user actually is.
  // scrollToIndex may need a frame to mount a row outside the current
  // overscan window, so retry once via requestAnimationFrame rather than
  // assuming it's already in the DOM synchronously after the state update
  // that requested it.
  const shouldFocusRef = useRef(false);
  useEffect(() => {
    if (!shouldFocusRef.current) return;
    shouldFocusRef.current = false;
    const targetIndex = activeIndex;
    const tryFocus = () => {
      const row = listContainerRef.current?.querySelector<HTMLElement>(
        `[data-track-index="${targetIndex}"]`
      );
      if (row) {
        row.focus();
      } else {
        requestAnimationFrame(tryFocus);
      }
    };
    tryFocus();
  }, [activeIndex]);

  const handleListboxKeyDown = useCallback((e: KeyboardEvent<HTMLDivElement>) => {
    if (tracks.length === 0) return;
    let next = activeIndex;
    switch (e.key) {
      case 'ArrowDown':
        next = Math.min(activeIndex + 1, tracks.length - 1);
        break;
      case 'ArrowUp':
        next = Math.max(activeIndex - 1, 0);
        break;
      case 'Home':
        next = 0;
        break;
      case 'End':
        next = tracks.length - 1;
        break;
      default:
        return;
    }
    e.preventDefault();
    if (next === activeIndex) return;
    virtualizer.scrollToIndex(next, { align: 'auto' });
    shouldFocusRef.current = true;
    setActiveIndex(next);
  }, [activeIndex, tracks.length, virtualizer]);

  // Keep the roving stop in sync with whatever row actually has DOM focus
  // (e.g. a mouse click) -- a row with tabIndex=-1 is still click-focusable,
  // so without this, a click could leave activeIndex pointing at a
  // different row than the one arrow keys would next move relative to.
  const handleListboxFocus = useCallback((e: FocusEvent<HTMLDivElement>) => {
    const indexAttr = (e.target as HTMLElement).getAttribute('data-track-index');
    if (indexAttr === null) return;
    const idx = Number(indexAttr);
    if (!Number.isNaN(idx)) {
      setActiveIndex((current) => (idx === current ? current : idx));
    }
  }, []);

  return (
    <ListViewContainer elevation={2}>
      <div
        ref={listContainerRef}
        role="listbox"
        aria-label="Track list"
        aria-multiselectable="true"
        onKeyDown={handleListboxKeyDown}
        onFocus={handleListboxFocus}
      >
        <div
          style={{
            height: virtualizer.getTotalSize(),
            width: '100%',
            position: 'relative',
          }}
        >
          {virtualItems.map((virtualRow) => {
            const track = tracks[virtualRow.index];
            return (
              <div
                key={track.id}
                style={{
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  width: '100%',
                  height: `${virtualRow.size}px`,
                  transform: `translateY(${virtualRow.start - (virtualizer.options.scrollMargin ?? 0)}px)`,
                }}
              >
                <SelectableTrackRow
                  track={track}
                  index={virtualRow.index}
                  isSelected={isSelected(track.id)}
                  tabIndex={virtualRow.index === activeIndex ? 0 : -1}
                  onToggleSelect={onToggleSelect}
                  isPlaying={isPlaying && currentTrackId === track.id}
                  isCurrent={currentTrackId === track.id}
                  isAnyPlaying={isPlaying}
                  onPlay={handlePlay}
                  onPause={onPause}
                  onEditMetadata={onEditMetadata}
                  onFindSimilar={onFindSimilar}
                />
              </div>
            );
          })}
        </div>
      </div>

      {/* Loading indicator */}
      {isLoadingMore && (
        <GridLoadingState current={tracks.length} total={totalTracks} itemType="tracks" />
      )}

      {/* End of list indicator */}
      {!hasMore && tracks.length > 0 && (
        <EndOfListIndicator count={totalTracks} itemType="tracks" />
      )}
    </ListViewContainer>
  );
};

export default TrackListViewContent;
