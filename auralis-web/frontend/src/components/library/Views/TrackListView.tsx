/**
 * TrackListView - Track List Rendering Component
 *
 * Handles rendering of tracks in either grid or list view mode.
 * Includes infinite scroll support and loading states.
 *
 * Extracted from CozyLibraryView.tsx for better separation of concerns.
 *
 * Features:
 * - Grid view with album cards
 * - List view with selectable track rows
 * - Infinite scroll with Intersection Observer
 * - Loading skeletons
 * - Virtual spacers for proper scrollbar length
 * - Queue integration
 */

import React from 'react';
import InfiniteScroll from 'react-infinite-scroll-component';
import { LibraryGridSkeleton, TrackRowSkeleton } from '@/components/shared/ui/loaders';
import { ListLoadingContainer } from '@/components/library/Styles/Grid.styles';
import GridLoadingState from '@/components/library/Items/utilities/GridLoadingState';
import TrackGridView from './TrackGridView';
import TrackListViewContent from './TrackListViewContent';
import { useQueueOperations } from './useQueueOperations';
import type { LibraryTrack } from '@/types/domain';

export type ViewMode = 'grid' | 'list';

export interface TrackListViewProps {
  tracks: LibraryTrack[];
  viewMode: ViewMode;
  loading: boolean;
  hasMore: boolean;
  totalTracks: number;
  isLoadingMore: boolean;
  currentTrackId?: number;
  isPlaying: boolean;

  // Selection (for list view)
  selectedTracks: Set<number>;
  isSelected: (trackId: number) => boolean;
  onToggleSelect: (trackId: number, e: React.MouseEvent) => void;

  // Actions
  onTrackPlay: (track: LibraryTrack) => void;
  onPause: () => void;
  onEditMetadata: (trackId: number) => void;
  onFindSimilar?: (trackId: number) => void; // Phase 5: Find similar tracks
  onLoadMore: () => void;
}

/**
 * Track List View Component
 *
 * Renders tracks in grid or list mode with infinite scroll support.
 */
export const TrackListView = ({
  tracks,
  viewMode,
  loading,
  hasMore,
  totalTracks,
  isLoadingMore,
  currentTrackId,
  isPlaying,
  selectedTracks,
  isSelected,
  onToggleSelect,
  onTrackPlay,
  onPause,
  onEditMetadata,
  onFindSimilar,
  onLoadMore,
}: TrackListViewProps) => {
  // Queue operations with toast feedback
  const {
    handleRemoveTrack,
    handleReorderQueue,
    handleShuffleQueue,
    handleClearQueue,
  } = useQueueOperations({});

  // Show loading skeletons
  if (loading) {
    return viewMode === 'grid' ? (
      <LibraryGridSkeleton count={12} />
    ) : (
      <ListLoadingContainer elevation={2}>
        {Array.from({ length: 8 }).map((_, index) => (
          <TrackRowSkeleton key={index} />
        ))}
      </ListLoadingContainer>
    );
  }

  // Grid View — wrapped in InfiniteScroll targeting the app scroll container
  if (viewMode === 'grid') {
    return (
      <InfiniteScroll
        dataLength={tracks.length}
        next={onLoadMore}
        hasMore={hasMore}
        loader={<GridLoadingState current={tracks.length} total={totalTracks} itemType="tracks" />}
        scrollableTarget="app-main-content-scroll"
        scrollThreshold={0.8}
      >
        <TrackGridView
          tracks={tracks}
          hasMore={false}
          currentTrackId={currentTrackId}
          onTrackPlay={onTrackPlay}
          onRemoveTrack={handleRemoveTrack}
          onReorderQueue={handleReorderQueue}
          onShuffleQueue={handleShuffleQueue}
          onClearQueue={handleClearQueue}
        />
      </InfiniteScroll>
    );
  }

  // List View — virtualizer handles its own infinite load trigger
  return (
    <TrackListViewContent
      tracks={tracks}
      hasMore={hasMore}
      isLoadingMore={loading || isLoadingMore}
      totalTracks={totalTracks}
      currentTrackId={currentTrackId}
      isPlaying={isPlaying}
      selectedTracks={selectedTracks}
      isSelected={isSelected}
      onToggleSelect={onToggleSelect}
      onTrackPlay={onTrackPlay}
      onPause={onPause}
      onEditMetadata={onEditMetadata}
      onFindSimilar={onFindSimilar}
      onLoadMore={onLoadMore}
    />
  );
};

export default TrackListView;
