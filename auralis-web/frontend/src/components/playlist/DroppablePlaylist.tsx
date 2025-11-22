/**
 * DroppablePlaylist.tsx
 *
 * Droppable playlist item that accepts track drops
 * Used in PlaylistList for drag-and-drop functionality
 */

import React from 'react';
import { Droppable } from '@hello-pangea/dnd';
import { styled } from '@mui/material/styles';
import { Box, ListItemButton, ListItemText, Typography } from '@mui/material';
import QueueMusicIcon from '@mui/icons-material/QueueMusic';
import { auroraOpacity } from '../library/Color.styles';

const StyledListItemButton = styled(ListItemButton, {
  shouldForwardProp: (prop) => prop !== 'isDraggingOver' && prop !== 'selected',
})<{ isDraggingOver?: boolean; selected?: boolean }>(({ theme, isDraggingOver, selected }) => ({
  borderRadius: theme.spacing(1),
  marginBottom: theme.spacing(0.5),
  padding: theme.spacing(1, 2),
  transition: 'all 0.2s ease',
  backgroundColor: isDraggingOver
    ? auroraOpacity.standard
    : selected
      ? auroraOpacity.veryLight
      : 'transparent',
  border: isDraggingOver ? `2px dashed ${auroraOpacity.stronger}` : '2px solid transparent',

  '&:hover': {
    backgroundColor: isDraggingOver
      ? auroraOpacity.light
      : selected
        ? auroraOpacity.lighter
        : 'rgba(255, 255, 255, 0.05)',
  },
}));

const PlaylistIcon = styled(QueueMusicIcon)(({ theme }) => ({
  marginRight: theme.spacing(2),
  color: theme.palette.text.secondary,
}));

const TrackCount = styled(Typography)(({ theme }) => ({
  fontSize: '0.75rem',
  color: theme.palette.text.secondary,
  marginLeft: theme.spacing(1),
}));

const DropIndicator = styled(Box)(({ theme }) => ({
  position: 'absolute',
  top: 0,
  left: 0,
  right: 0,
  bottom: 0,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  backgroundColor: auroraOpacity.veryLight,
  border: `2px dashed ${auroraOpacity.stronger}`,
  borderRadius: theme.spacing(1),
  pointerEvents: 'none',
  zIndex: 1,
}));

const DropIndicatorText = styled(Typography)(({ theme }) => ({
  color: theme.palette.primary.main,
  fontWeight: 600,
  fontSize: '0.875rem',
}));

interface DroppablePlaylistProps {
  playlistId: number;
  playlistName: string;
  trackCount: number;
  selected?: boolean;
  onClick?: () => void;
  onContextMenu?: (e: React.MouseEvent) => void;
}

export const DroppablePlaylist: React.FC<DroppablePlaylistProps> = ({
  playlistId,
  playlistName,
  trackCount,
  selected = false,
  onClick,
  onContextMenu,
}) => {
  const droppableId = `playlist-${playlistId}`;

  return (
    <Droppable droppableId={droppableId} type="TRACK">
      {(provided, snapshot) => (
        <Box
          ref={provided.innerRef}
          {...provided.droppableProps}
          sx={{ position: 'relative' }}
        >
          <StyledListItemButton
            selected={selected}
            isDraggingOver={snapshot.isDraggingOver}
            onClick={onClick}
            onContextMenu={onContextMenu}
          >
            <PlaylistIcon fontSize="small" />
            <ListItemText
              primary={playlistName}
              secondary={
                <TrackCount>
                  {trackCount} {trackCount === 1 ? 'track' : 'tracks'}
                </TrackCount>
              }
            />
          </StyledListItemButton>

          {snapshot.isDraggingOver && (
            <DropIndicator>
              <DropIndicatorText>Drop to add tracks</DropIndicatorText>
            </DropIndicator>
          )}

          {/* Hidden placeholder for dnd */}
          <Box sx={{ display: 'none' }}>{provided.placeholder}</Box>
        </Box>
      )}
    </Droppable>
  );
};
