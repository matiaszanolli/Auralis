/**
 * SelectableTrackRow Component
 *
 * Wrapper around TrackRow that adds selection checkbox and multi-select support.
 *
 * Usage:
 * ```tsx
 * <SelectableTrackRow
 *   track={track}
 *   index={index}
 *   isSelected={isSelected(track.id)}
 *   onToggleSelect={(e) => toggleTrack(track.id, e)}
 *   onPlay={handlePlay}
 *   onPause={handlePause}
 * />
 * ```
 */

import React, { useCallback } from 'react';
import TrackRow from './TrackRow';
import { SelectableContainer, StyledCheckbox, TrackContainer } from './SelectableTrackRow.styles';
import { useTrackRowSelection } from './useTrackRowSelection';

import type { LibraryTrack as Track } from '@/types/domain';

interface SelectableTrackRowProps {
  track: Track;
  index: number;
  isSelected: boolean;
  onToggleSelect: (trackId: number, event: React.MouseEvent) => void;
  isPlaying?: boolean;
  isCurrent?: boolean;
  isAnyPlaying?: boolean; // Phase 1: Global playback state
  onPlay: (trackId: number) => void;
  onPause?: () => void;
  onDoubleClick?: (trackId: number) => void;
  onEditMetadata?: (trackId: number) => void;
  onFindSimilar?: (trackId: number) => void; // Phase 5: Find similar tracks
  onToggleFavorite?: (trackId: number) => void;
  onShowAlbum?: (albumId: number) => void;
  onShowArtist?: (artistName: string) => void;
  onShowInfo?: (trackId: number) => void;
  onDelete?: (trackId: number) => void;
}

const SelectableTrackRow = ({
  track,
  index,
  isSelected,
  onToggleSelect,
  isPlaying,
  isCurrent,
  isAnyPlaying,
  onPlay,
  onPause,
  onDoubleClick,
  onEditMetadata,
  onFindSimilar,
  onToggleFavorite,
  onShowAlbum,
  onShowArtist,
  onShowInfo,
  onDelete,
}: SelectableTrackRowProps) => {
  // Bind track.id to the selection handler so the parent can pass a
  // single stable callback for all rows (fixes inline arrow in #3413)
  const boundToggleSelect = useCallback(
    (event: React.MouseEvent) => onToggleSelect(track.id, event),
    [onToggleSelect, track.id]
  );

  const { handleContainerClick, handleCheckboxClick } = useTrackRowSelection({
    onToggleSelect: boundToggleSelect,
  });

  return (
    <SelectableContainer
      isSelected={isSelected}
      onClick={handleContainerClick}
    >
      <StyledCheckbox
        className={`selection-checkbox ${isSelected ? 'visible' : ''}`}
        checked={isSelected}
        onClick={handleCheckboxClick}
        size="small"
        inputProps={{ 'aria-label': `Select ${track.title}` }}
      />
      <TrackContainer>
        <TrackRow
          track={track}
          index={index}
          isPlaying={isPlaying}
          isCurrent={isCurrent}
          isAnyPlaying={isAnyPlaying}
          onPlay={onPlay}
          onPause={onPause}
          onDoubleClick={onDoubleClick}
          onEditMetadata={onEditMetadata}
          onFindSimilar={onFindSimilar}
          onToggleFavorite={onToggleFavorite}
          onShowAlbum={onShowAlbum}
          onShowArtist={onShowArtist}
          onShowInfo={onShowInfo}
          onDelete={onDelete}
        />
      </TrackContainer>
    </SelectableContainer>
  );
};

export default React.memo(SelectableTrackRow);
