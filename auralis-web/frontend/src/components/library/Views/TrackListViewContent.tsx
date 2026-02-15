import React, { useRef, useEffect } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import SelectableTrackRow from '../Items/tracks/SelectableTrackRow';
import GridLoadingState from '../Items/utilities/GridLoadingState';
import EndOfListIndicator from '../Items/utilities/EndOfListIndicator';
import { ListViewContainer, VirtualScrollContainer } from './TrackListView.styles';
import { Track } from './TrackListView';

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
  onToggleSelect: (trackId: number, e: React.MouseEvent) => void;
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
export const TrackListViewContent: React.FC<TrackListViewContentProps> = ({
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
}) => {
  const parentRef = useRef<HTMLDivElement>(null);

  const virtualizer = useVirtualizer({
    count: tracks.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 5,
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

  return (
    <ListViewContainer elevation={2}>
      <VirtualScrollContainer ref={parentRef}>
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
                  transform: `translateY(${virtualRow.start}px)`,
                }}
              >
                <SelectableTrackRow
                  track={track}
                  index={virtualRow.index}
                  isSelected={isSelected(track.id)}
                  onToggleSelect={(e) => onToggleSelect(track.id, e)}
                  isPlaying={isPlaying && currentTrackId === track.id}
                  isCurrent={currentTrackId === track.id}
                  isAnyPlaying={isPlaying}
                  onPlay={(trackId) => {
                    const foundTrack = tracks.find((t) => t.id === trackId);
                    if (foundTrack) {
                      onTrackPlay(foundTrack);
                    }
                  }}
                  onPause={onPause}
                  onEditMetadata={onEditMetadata}
                  onFindSimilar={onFindSimilar}
                />
              </div>
            );
          })}
        </div>
      </VirtualScrollContainer>

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
