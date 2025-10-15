import React from 'react';
import { Box, Typography, List, ListItem, ListItemText, styled } from '@mui/material';
import { PlayArrow } from '@mui/icons-material';
import { colors, gradients } from '../../theme/auralisTheme';

interface Track {
  id: number;
  title: string;
  artist?: string;
  duration: number;
}

interface TrackQueueProps {
  tracks: Track[];
  currentTrackId?: number;
  onTrackClick?: (trackId: number) => void;
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

const QueueHeader = styled(Typography)(({ theme }) => ({
  fontSize: '14px',
  fontWeight: 600,
  color: colors.text.secondary,
  textTransform: 'uppercase',
  letterSpacing: '0.5px',
  marginBottom: '12px',
  paddingLeft: '8px',
}));

const QueueList = styled(List)({
  padding: 0,
  '& .MuiListItem-root': {
    padding: 0,
  },
});

const TrackItem = styled(ListItem)<{ isactive?: string }>(({ isactive }) => ({
  height: '48px',
  padding: '0 12px',
  borderRadius: '6px',
  cursor: 'pointer',
  transition: 'all 0.2s ease',
  marginBottom: '4px',
  background: isactive === 'true' ? 'rgba(102, 126, 234, 0.15)' : 'transparent',
  border: isactive === 'true' ? `1px solid rgba(102, 126, 234, 0.3)` : '1px solid transparent',
  position: 'relative',

  '&:hover': {
    background: isactive === 'true'
      ? 'rgba(102, 126, 234, 0.2)'
      : colors.background.hover,
    transform: 'translateX(4px)',

    '& .play-indicator': {
      opacity: 1,
    },
  },

  '&:last-child': {
    marginBottom: 0,
  },
}));

const TrackNumber = styled(Typography)<{ isactive?: string }>(({ isactive }) => ({
  fontSize: '14px',
  fontWeight: 500,
  color: isactive === 'true' ? '#667eea' : colors.text.secondary,
  minWidth: '32px',
  textAlign: 'center',
  transition: 'color 0.2s ease',
}));

const TrackTitle = styled(Typography)<{ isactive?: string }>(({ isactive }) => ({
  fontSize: '14px',
  fontWeight: isactive === 'true' ? 600 : 400,
  color: isactive === 'true' ? colors.text.primary : colors.text.primary,
  flex: 1,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
  paddingRight: '12px',
  transition: 'all 0.2s ease',
}));

const TrackDuration = styled(Typography)<{ isactive?: string }>(({ isactive }) => ({
  fontSize: '14px',
  fontWeight: 400,
  color: isactive === 'true' ? colors.text.secondary : colors.text.disabled,
  minWidth: '50px',
  textAlign: 'right',
  transition: 'color 0.2s ease',
}));

const PlayIndicator = styled(PlayArrow)({
  position: 'absolute',
  left: '8px',
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

export const TrackQueue: React.FC<TrackQueueProps> = ({
  tracks,
  currentTrackId,
  onTrackClick,
  title = 'Queue',
}) => {
  const formatDuration = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  if (!tracks || tracks.length === 0) {
    return null;
  }

  return (
    <QueueContainer>
      <QueueHeader>{title}</QueueHeader>
      <QueueList>
        {tracks.map((track, index) => {
          const isActive = currentTrackId === track.id;
          const isActiveStr = isActive ? 'true' : 'false';

          return (
            <TrackItem
              key={track.id}
              isactive={isActiveStr}
              onClick={() => onTrackClick?.(track.id)}
            >
              {isActive && <ActiveIndicator />}
              <PlayIndicator className="play-indicator" />

              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  width: '100%',
                  gap: 2,
                  paddingLeft: isActive ? '12px' : '0',
                  transition: 'padding-left 0.2s ease',
                }}
              >
                <TrackNumber isactive={isActiveStr}>
                  {index + 1}
                </TrackNumber>

                <TrackTitle isactive={isActiveStr}>
                  {track.title}
                </TrackTitle>

                <TrackDuration isactive={isActiveStr}>
                  {formatDuration(track.duration)}
                </TrackDuration>
              </Box>
            </TrackItem>
          );
        })}
      </QueueList>
    </QueueContainer>
  );
};

export default TrackQueue;
