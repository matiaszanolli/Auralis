import React from 'react';
import { Box } from '@mui/material';
import SelectableTrackRow from '../Items/SelectableTrackRow';
import InfiniteScrollTrigger from '../Items/InfiniteScrollTrigger';
import GridLoadingState from '../Items/GridLoadingState';
import EndOfListIndicator from '../Items/EndOfListIndicator';
import { ListViewContainer, TrackItemWrapper } from './TrackListView.styles';
import { Track } from './TrackListView';

export interface TrackListViewContentProps {
  tracks: Track[];
  hasMore: boolean;
  isLoadingMore: boolean;
  totalTracks: number;
  currentTrackId?: number;
  isPlaying: boolean;
  selectedTracks: Set<number>;
  isSelected: (trackId: number) => boolean;
  loadMoreRef: React.RefObject<HTMLDivElement>;
  onToggleSelect: (trackId: number, e: React.MouseEvent) => void;
  onTrackPlay: (track: Track) => void;
  onPause: () => void;
  onEditMetadata: (trackId: number) => void;
}

/**
 * TrackListViewContent - List layout for track rows
 *
 * Displays tracks as selectable rows with metadata.
 */
export const TrackListViewContent: React.FC<TrackListViewContentProps> = ({
  tracks,
  hasMore,
  isLoadingMore,
  totalTracks,
  currentTrackId,
  isPlaying,
  selectedTracks,
  isSelected,
  loadMoreRef,
  onToggleSelect,
  onTrackPlay,
  onPause,
  onEditMetadata,
}) => {
  return (
    <ListViewContainer elevation={2}>
      {tracks.map((track, index) => (
        <TrackItemWrapper
          key={track.id}
          className="animate-fade-in-left"
          sx={{
            animationDelay: `${index * 0.03}s`,
            animationFillMode: 'both',
          }}
        >
          <SelectableTrackRow
            track={track}
            index={index}
            isSelected={isSelected(track.id)}
            onToggleSelect={(e) => onToggleSelect(track.id, e)}
            isPlaying={isPlaying}
            isCurrent={currentTrackId === track.id}
            onPlay={(trackId) => {
              const foundTrack = tracks.find((t) => t.id === trackId);
              if (foundTrack) {
                onTrackPlay(foundTrack);
              }
            }}
            onPause={onPause}
            onEditMetadata={onEditMetadata}
          />
        </TrackItemWrapper>
      ))}

      {/* Intersection observer trigger for infinite scroll */}
      {hasMore && <InfiniteScrollTrigger ref={loadMoreRef} />}

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
