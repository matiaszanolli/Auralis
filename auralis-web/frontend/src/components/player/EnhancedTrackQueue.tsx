import React, { useState } from 'react';
import {
  Box,
  Typography,
  List,
  ListItem,
  IconButton,
  Button,
  styled,
  Tooltip,
} from '@mui/material';
import {
  PlayArrow,
  Close,
  Shuffle,
  ClearAll,
  DragIndicator,
} from '@mui/icons-material';
import { DragDropContext, Droppable, Draggable, DropResult } from '@hello-pangea/dnd';
import { colors, gradients } from '../../theme/auralisTheme';
import { useToast } from '../shared/Toast';

interface Track {
  id: number;
  title: string;
  artist?: string;
  duration: number;
}

interface EnhancedTrackQueueProps {
  tracks: Track[];
  currentTrackId?: number;
  onTrackClick?: (trackId: number) => void;
  onRemoveTrack?: (index: number) => void;
  onReorderQueue?: (newOrder: number[]) => void;
  onClearQueue?: () => void;
  onShuffleQueue?: () => void;
  title?: string;
}

const QueueContainer = styled(Box)(({ theme }) => ({
  width: '100%',
  background: colors.background.secondary,
  borderRadius: '8px',
  padding: '16px',
  marginTop: '24px',
  border: `1px solid rgba(102, 126, 234, 0.1)`,
}));

const QueueHeader = styled(Box)({
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  marginBottom: '12px',
  paddingLeft: '8px',
});

const QueueTitle = styled(Typography)({
  fontSize: '14px',
  fontWeight: 600,
  color: colors.text.secondary,
  textTransform: 'uppercase',
  letterSpacing: '0.5px',
});

const QueueControls = styled(Box)({
  display: 'flex',
  gap: '8px',
});

const QueueButton = styled(IconButton)({
  width: '32px',
  height: '32px',
  color: colors.text.secondary,
  transition: 'all 0.2s ease',

  '&:hover': {
    color: '#667eea',
    background: 'rgba(102, 126, 234, 0.1)',
    transform: 'scale(1.1)',
  },

  '& .MuiSvgIcon-root': {
    fontSize: '20px',
  },
});

const QueueList = styled(List)({
  padding: 0,
  '& .MuiListItem-root': {
    padding: 0,
  },
});

const TrackItem = styled(Box)<{ isactive?: string; isdragging?: string }>(
  ({ isactive, isdragging }) => ({
    height: '48px',
    padding: '0 12px',
    borderRadius: '6px',
    cursor: 'pointer',
    transition: 'all 0.2s ease',
    marginBottom: '4px',
    background:
      isdragging === 'true'
        ? 'rgba(102, 126, 234, 0.25)'
        : isactive === 'true'
        ? 'rgba(102, 126, 234, 0.15)'
        : 'transparent',
    border:
      isactive === 'true'
        ? `1px solid rgba(102, 126, 234, 0.3)`
        : '1px solid transparent',
    position: 'relative',
    display: 'flex',
    alignItems: 'center',
    gap: '8px',

    '&:hover': {
      background:
        isdragging === 'true'
          ? 'rgba(102, 126, 234, 0.25)'
          : isactive === 'true'
          ? 'rgba(102, 126, 234, 0.2)'
          : colors.background.hover,
      transform: isdragging === 'true' ? 'scale(1.02)' : 'translateX(4px)',

      '& .play-indicator': {
        opacity: 1,
      },

      '& .remove-button': {
        opacity: 1,
      },
    },

    '&:last-child': {
      marginBottom: 0,
    },
  })
);

const DragHandle = styled(Box)({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  width: '24px',
  color: colors.text.disabled,
  cursor: 'grab',
  transition: 'color 0.2s ease',

  '&:active': {
    cursor: 'grabbing',
  },

  '&:hover': {
    color: colors.text.secondary,
  },

  '& .MuiSvgIcon-root': {
    fontSize: '18px',
  },
});

const TrackNumber = styled(Typography)<{ isactive?: string }>(({ isactive }) => ({
  fontSize: '14px',
  fontWeight: 500,
  color: isactive === 'true' ? '#667eea' : colors.text.secondary,
  minWidth: '32px',
  textAlign: 'center',
  transition: 'color 0.2s ease',
}));

const TrackInfo = styled(Box)({
  flex: 1,
  display: 'flex',
  flexDirection: 'column',
  overflow: 'hidden',
  minWidth: 0,
});

const TrackTitle = styled(Typography)<{ isactive?: string }>(({ isactive }) => ({
  fontSize: '14px',
  fontWeight: isactive === 'true' ? 600 : 400,
  color: isactive === 'true' ? colors.text.primary : colors.text.primary,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
  transition: 'all 0.2s ease',
}));

const TrackArtist = styled(Typography)({
  fontSize: '12px',
  color: colors.text.secondary,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
});

const TrackDuration = styled(Typography)<{ isactive?: string }>(({ isactive }) => ({
  fontSize: '14px',
  fontWeight: 400,
  color: isactive === 'true' ? colors.text.secondary : colors.text.disabled,
  minWidth: '50px',
  textAlign: 'right',
  transition: 'color 0.2s ease',
}));

const RemoveButton = styled(IconButton)({
  width: '28px',
  height: '28px',
  color: colors.text.secondary,
  opacity: 0,
  transition: 'all 0.2s ease',

  '&:hover': {
    color: '#f44336',
    background: 'rgba(244, 67, 54, 0.1)',
  },

  '& .MuiSvgIcon-root': {
    fontSize: '18px',
  },
});

const PlayIndicator = styled(PlayArrow)({
  position: 'absolute',
  left: '40px',
  fontSize: '16px',
  color: '#667eea',
  opacity: 0,
  transition: 'opacity 0.2s ease',
});

const ActiveIndicator = styled(Box)({
  position: 'absolute',
  left: 0,
  top: 0,
  bottom: 0,
  width: '3px',
  background: gradients.aurora,
  borderRadius: '0 2px 2px 0',
});

const EmptyState = styled(Box)({
  textAlign: 'center',
  padding: '24px',
  color: colors.text.secondary,
});

export const EnhancedTrackQueue: React.FC<EnhancedTrackQueueProps> = ({
  tracks,
  currentTrackId,
  onTrackClick,
  onRemoveTrack,
  onReorderQueue,
  onClearQueue,
  onShuffleQueue,
  title = 'Queue',
}) => {
  const { success, info, warning, showError } = useToast();
  const [isShuffling, setIsShuffling] = useState(false);
  const [isClearing, setIsClearing] = useState(false);

  const formatDuration = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const handleDragEnd = (result: DropResult) => {
    if (!result.destination || !onReorderQueue) {
      return;
    }

    const sourceIndex = result.source.index;
    const destIndex = result.destination.index;

    if (sourceIndex === destIndex) {
      return;
    }

    // Create new order array
    const newOrder = Array.from(Array(tracks.length).keys());
    const [removed] = newOrder.splice(sourceIndex, 1);
    newOrder.splice(destIndex, 0, removed);

    info('Reordering queue...');
    onReorderQueue(newOrder);
  };

  const handleRemove = async (index: number, trackTitle: string) => {
    if (!onRemoveTrack) return;

    try {
      onRemoveTrack(index);
      success(`Removed "${trackTitle}" from queue`);
    } catch (error) {
      showError('Failed to remove track from queue');
    }
  };

  const handleShuffle = async () => {
    if (!onShuffleQueue || isShuffling) return;

    setIsShuffling(true);
    try {
      onShuffleQueue();
      success('Queue shuffled');
    } catch (error) {
      showError('Failed to shuffle queue');
    } finally {
      setTimeout(() => setIsShuffling(false), 500);
    }
  };

  const handleClear = async () => {
    if (!onClearQueue || isClearing) return;

    // Simple confirmation via toast
    if (!window.confirm('Clear entire queue?')) {
      return;
    }

    setIsClearing(true);
    try {
      onClearQueue();
      info('Queue cleared');
    } catch (error) {
      showError('Failed to clear queue');
    } finally {
      setTimeout(() => setIsClearing(false), 500);
    }
  };

  if (!tracks || tracks.length === 0) {
    return (
      <QueueContainer>
        <QueueHeader>
          <QueueTitle>{title}</QueueTitle>
        </QueueHeader>
        <EmptyState>
          <Typography variant="body2" color="textSecondary">
            Queue is empty
          </Typography>
          <Typography variant="caption" color="textSecondary">
            Add tracks to start playback
          </Typography>
        </EmptyState>
      </QueueContainer>
    );
  }

  return (
    <QueueContainer>
      <QueueHeader>
        <QueueTitle>
          {title} ({tracks.length} {tracks.length === 1 ? 'track' : 'tracks'})
        </QueueTitle>
        <QueueControls>
          {onShuffleQueue && (
            <Tooltip title="Shuffle queue">
              <QueueButton onClick={handleShuffle} disabled={isShuffling}>
                <Shuffle />
              </QueueButton>
            </Tooltip>
          )}
          {onClearQueue && (
            <Tooltip title="Clear queue">
              <QueueButton onClick={handleClear} disabled={isClearing}>
                <ClearAll />
              </QueueButton>
            </Tooltip>
          )}
        </QueueControls>
      </QueueHeader>

      <DragDropContext onDragEnd={handleDragEnd}>
        <Droppable droppableId="queue">
          {(provided, snapshot) => (
            <QueueList ref={provided.innerRef} {...provided.droppableProps}>
              {tracks.map((track, index) => {
                const isActive = currentTrackId === track.id;
                const isActiveStr = isActive ? 'true' : 'false';

                return (
                  <Draggable
                    key={track.id}
                    draggableId={String(track.id)}
                    index={index}
                    isDragDisabled={!onReorderQueue}
                  >
                    {(provided, snapshot) => (
                      <ListItem
                        ref={provided.innerRef}
                        {...provided.draggableProps}
                      >
                        <TrackItem
                          isactive={isActiveStr}
                          isdragging={snapshot.isDragging ? 'true' : 'false'}
                          onClick={() => onTrackClick?.(track.id)}
                        >
                          {isActive && <ActiveIndicator />}
                          <PlayIndicator className="play-indicator" />

                          {onReorderQueue && (
                            <DragHandle {...provided.dragHandleProps}>
                              <DragIndicator />
                            </DragHandle>
                          )}

                          <TrackNumber isactive={isActiveStr}>
                            {index + 1}
                          </TrackNumber>

                          <TrackInfo>
                            <TrackTitle isactive={isActiveStr}>
                              {track.title}
                            </TrackTitle>
                            {track.artist && (
                              <TrackArtist>{track.artist}</TrackArtist>
                            )}
                          </TrackInfo>

                          <TrackDuration isactive={isActiveStr}>
                            {formatDuration(track.duration)}
                          </TrackDuration>

                          {onRemoveTrack && (
                            <Tooltip title="Remove from queue">
                              <RemoveButton
                                className="remove-button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleRemove(index, track.title);
                                }}
                              >
                                <Close />
                              </RemoveButton>
                            </Tooltip>
                          )}
                        </TrackItem>
                      </ListItem>
                    )}
                  </Draggable>
                );
              })}
              {provided.placeholder}
            </QueueList>
          )}
        </Droppable>
      </DragDropContext>
    </QueueContainer>
  );
};

export default EnhancedTrackQueue;
