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
import { Box, Checkbox, styled } from '@mui/material';
import TrackRow from './TrackRow';

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

const SelectableContainer = styled(Box, {
  shouldForwardProp: (prop) => prop !== 'isSelected',
})<{ isSelected: boolean }>(({ theme, isSelected }) => ({
  display: 'flex',
  alignItems: 'center',
  gap: '8px',
  padding: '4px 8px',
  borderRadius: '8px',
  backgroundColor: isSelected ? 'rgba(102, 126, 234, 0.15)' : 'transparent',
  border: isSelected ? '1px solid rgba(102, 126, 234, 0.3)' : '1px solid transparent',
  transition: 'all 0.2s ease',
  cursor: 'pointer',
  '&:hover': {
    backgroundColor: isSelected ? 'rgba(102, 126, 234, 0.2)' : 'rgba(255, 255, 255, 0.03)',
    '& .selection-checkbox': {
      opacity: 1,
    },
  },
}));

const StyledCheckbox = styled(Checkbox)(({ theme }) => ({
  color: 'rgba(255, 255, 255, 0.3)',
  opacity: 0,
  transition: 'opacity 0.2s ease',
  '&.Mui-checked': {
    color: '#667eea',
    opacity: 1,
  },
  '&.visible': {
    opacity: 1,
  },
  '& .MuiSvgIcon-root': {
    fontSize: '20px',
  },
}));

const TrackContainer = styled(Box)(({ theme }) => ({
  flex: 1,
  minWidth: 0, // Allow text truncation
}));

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
  const handleContainerClick = (event: React.MouseEvent) => {
    // Don't trigger selection if clicking on action buttons
    const target = event.target as HTMLElement;
    const isActionButton = target.closest('button') || target.closest('[role="button"]');
    
    if (!isActionButton) {
      onToggleSelect(event);
    }
  };

  const handleCheckboxClick = (event: React.MouseEvent) => {
    event.stopPropagation();
    onToggleSelect(event);
  };

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
