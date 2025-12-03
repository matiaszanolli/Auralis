/**
 * TrackPlayIndicator - Play/pause indicator for track row
 */

import React from 'react';
import { TableCell, Box, Typography } from '@mui/material';
import { PlayArrow, Pause } from '@mui/icons-material';
import { PlayIcon } from '../../Styles/Table.styles';
import { tokens } from '@/design-system/tokens';

interface TrackPlayIndicatorProps {
  isCurrentTrack: boolean;
  isPlaying: boolean;
  trackNumber?: number;
  index: number;
}

export const TrackPlayIndicator: React.FC<TrackPlayIndicatorProps> = ({
  isCurrentTrack,
  isPlaying,
  trackNumber,
  index,
}) => {
  return (
    <TableCell>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        {isCurrentTrack && isPlaying ? (
          <Pause sx={{ fontSize: 20, color: tokens.colors.accent.primary }} />
        ) : (
          <>
            <Typography
              className="track-number"
              sx={{
                fontSize: '0.9rem',
                color: 'text.secondary',
                '.current-track &': { display: 'none' },
              }}
            >
              {trackNumber || index + 1}
            </Typography>
            <PlayIcon className="play-icon">
              <PlayArrow sx={{ fontSize: 20 }} />
            </PlayIcon>
          </>
        )}
      </Box>
    </TableCell>
  );
};

export default TrackPlayIndicator;
