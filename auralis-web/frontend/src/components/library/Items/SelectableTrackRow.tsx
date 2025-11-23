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

import React from 'react';
import TrackRow from './TrackRow';
import { SelectableContainer, StyledCheckbox, TrackContainer } from './SelectableTrackRow.styles';
import { useTrackRowSelection } from './useTrackRowSelection';

interface Track {
  id: number;
  title: string;
  artist: string;
  album: string;
  duration: number;
  albumArt?: string;
  isEnhanced?: boolean;
  quality?: number;
  genre?: string;
  year?: number;
  [key: string]: any;
}

interface SelectableTrackRowProps {
  track: Track;
  index: number;
  isSelected: boolean;
  onToggleSelect: (event: React.MouseEvent) => void;
  isPlaying?: boolean;
  isCurrent?: boolean;
  onPlay?: (trackId: number) => void;
  onPause?: () => void;
  onEditMetadata?: (trackId: number) => void;
  onAddToQueue?: (trackId: number) => void;
  onAddToPlaylist?: (trackId: number) => void;
}

const SelectableTrackRow: React.FC<SelectableTrackRowProps> = ({
  track,
  index,
  isSelected,
  onToggleSelect,
  isPlaying,
  isCurrent,
  onPlay,
  onPause,
  onEditMetadata,
  onAddToQueue,
  onAddToPlaylist,
}) => {
  const { handleContainerClick, handleCheckboxClick } = useTrackRowSelection({
    onToggleSelect,
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
      />
      <TrackContainer>
        <TrackRow
          track={track}
          index={index}
          isPlaying={isPlaying}
          isCurrent={isCurrent}
          onPlay={onPlay}
          onPause={onPause}
          onEditMetadata={onEditMetadata}
          onAddToQueue={onAddToQueue}
          onAddToPlaylist={onAddToPlaylist}
        />
      </TrackContainer>
    </SelectableContainer>
  );
};

export default SelectableTrackRow;
