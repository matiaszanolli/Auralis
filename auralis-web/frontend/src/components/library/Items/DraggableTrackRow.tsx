/**
 * DraggableTrackRow.tsx
 *
 * Draggable version of TrackRow component with @hello-pangea/dnd integration
 * Supports drag to playlists, queue, and reordering within playlists
 */

import React from 'react';
import { Draggable } from '@hello-pangea/dnd';
import { TrackRow, Track } from './TrackRow';
import { styled } from '@mui/material/styles';
import { Box } from '@mui/material';
import DragIndicatorIcon from '@mui/icons-material/DragIndicator';

const DragHandle = styled(Box)(({ theme }) => ({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  width: '24px',
  marginRight: theme.spacing(1),
  cursor: 'grab',
  color: theme.palette.text.secondary,
  opacity: 0.6,
  transition: 'opacity 0.2s ease',

  '&:hover': {
    opacity: 1,
  },

  '&:active': {
    cursor: 'grabbing',
  },
}));

const DraggableContainer = styled(Box, {
  shouldForwardProp: (prop) => prop !== 'isDragging',
})<{ isDragging?: boolean }>(({ isDragging }) => ({
  display: 'flex',
  alignItems: 'center',
  opacity: isDragging ? 0.5 : 1,
  transition: 'opacity 0.2s ease',
}));

interface DraggableTrackRowProps {
  track: Track;
  index: number;
  draggableId: string;
  isPlaying?: boolean;
  isCurrent?: boolean;
  isDragDisabled?: boolean;
  showDragHandle?: boolean;
  onPlay: (trackId: number) => void;
  onPause?: () => void;
  onDoubleClick?: (trackId: number) => void;
  onEditMetadata?: (trackId: number) => void;
  onToggleFavorite?: (trackId: number) => void;
  onShowAlbum?: (albumId: number) => void;
  onShowArtist?: (artistName: string) => void;
  onShowInfo?: (trackId: number) => void;
  onDelete?: (trackId: number) => void;
}

export const DraggableTrackRow: React.FC<DraggableTrackRowProps> = ({
  track,
  index,
  draggableId,
  isPlaying,
  isCurrent,
  isDragDisabled = false,
  showDragHandle = true,
  onPlay,
  onPause,
  onDoubleClick,
  onEditMetadata,
  onToggleFavorite,
  onShowAlbum,
  onShowArtist,
  onShowInfo,
  onDelete,
}) => {
  return (
    <Draggable
      draggableId={draggableId}
      index={index}
      isDragDisabled={isDragDisabled}
    >
      {(provided, snapshot) => (
        <DraggableContainer
          ref={provided.innerRef}
          {...provided.draggableProps}
          isDragging={snapshot.isDragging}
        >
          {showDragHandle && (
            <DragHandle {...provided.dragHandleProps}>
              <DragIndicatorIcon fontSize="small" />
            </DragHandle>
          )}
          <Box sx={{ flex: 1 }}>
            <TrackRow
              track={track}
              index={index}
              isPlaying={isPlaying}
              isCurrent={isCurrent}
              onPlay={onPlay}
              onPause={onPause}
              onDoubleClick={onDoubleClick}
              onEditMetadata={onEditMetadata}
              onToggleFavorite={onToggleFavorite}
              onShowAlbum={onShowAlbum}
              onShowArtist={onShowArtist}
              onShowInfo={onShowInfo}
              onDelete={onDelete}
            />
          </Box>
        </DraggableContainer>
      )}
    </Draggable>
  );
};
