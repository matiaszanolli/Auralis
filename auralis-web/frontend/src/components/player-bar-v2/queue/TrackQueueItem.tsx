/**
 * TrackQueueItem Component
 *
 * Individual track item in the queue
 */

import React from 'react';
import { Box } from '@mui/material';
import {
  TrackItem,
  TrackNumber,
  TrackTitle,
  TrackDuration,
  PlayIndicator,
  ActiveIndicator,
} from './TrackQueueStyles';
import { formatDuration } from './TrackQueueHelpers';

interface Track {
  id: number;
  title: string;
  artist?: string;
  duration: number;
}

interface TrackQueueItemProps {
  track: Track;
  index: number;
  isActive: boolean;
  onTrackClick: (trackId: number) => void;
  onContextMenu: (e: React.MouseEvent, track: Track) => void;
}

export const TrackQueueItem: React.FC<TrackQueueItemProps> = ({
  track,
  index,
  isActive,
  onTrackClick,
  onContextMenu,
}) => {
  const isActiveStr = isActive ? 'true' : 'false';

  return (
    <TrackItem
      isactive={isActiveStr}
      onClick={() => onTrackClick(track.id)}
      onContextMenu={(e) => onContextMenu(e, track)}
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
};
