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

import React, { useRef } from 'react';
import { LibraryGridSkeleton, TrackRowSkeleton } from '../../shared/ui/loaders';
import { ListLoadingContainer } from '../Styles/Grid.styles';
import TrackGridView from './TrackGridView';
import TrackListViewContent from './TrackListViewContent';
import { useQueueOperations } from './useQueueOperations';
import { useInfiniteScroll } from './useInfiniteScroll';

export interface Track {
  id: number;
  title: string;
  artist: string;
  album: string;
  album_id?: number;
  duration: number;
  albumArt?: string;
  quality?: number;
  isEnhanced?: boolean;
  genre?: string;
  year?: number;
}

export type ViewMode = 'grid' | 'list';

export interface TrackListViewProps {
  tracks: Track[];
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
  onTrackPlay: (track: Track) => void;
  onPause: () => void;
  onEditMetadata: (trackId: number) => void;
  onLoadMore: () => void;
}

/**
 * Track List View Component
 *
 * Renders tracks in grid or list mode with infinite scroll support.
 */
export const TrackListView: React.FC<TrackListViewProps> = ({
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
  onLoadMore,
}) => {
  const loadMoreRef = useRef<HTMLDivElement>(null);

  // Queue operations with toast feedback
  const {
    handleRemoveTrack,
    handleReorderQueue,
    handleShuffleQueue,
    handleClearQueue,
  } = useQueueOperations({});

  // Setup infinite scroll observer
  useInfiniteScroll({
    hasMore,
    isLoadingMore,
    isLoading: loading,
    onLoadMore,
    loadMoreRef,
  });

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

  // Grid View
  if (viewMode === 'grid') {
    return (
      <TrackGridView
        tracks={tracks}
        hasMore={hasMore}
        currentTrackId={currentTrackId}
        loadMoreRef={loadMoreRef}
        onTrackPlay={onTrackPlay}
        onRemoveTrack={handleRemoveTrack}
        onReorderQueue={handleReorderQueue}
        onShuffleQueue={handleShuffleQueue}
        onClearQueue={handleClearQueue}
      />
    );
  }

  // List View
  return (
    <TrackListViewContent
      tracks={tracks}
      hasMore={hasMore}
      isLoadingMore={isLoadingMore}
      totalTracks={totalTracks}
      currentTrackId={currentTrackId}
      isPlaying={isPlaying}
      selectedTracks={selectedTracks}
      isSelected={isSelected}
      loadMoreRef={loadMoreRef}
      onToggleSelect={onToggleSelect}
      onTrackPlay={onTrackPlay}
      onPause={onPause}
      onEditMetadata={onEditMetadata}
    />
  );
};

export default TrackListView;
