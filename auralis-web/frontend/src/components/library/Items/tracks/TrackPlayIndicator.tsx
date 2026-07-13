/**
 * TrackPlayIndicator - Play/pause indicator for track row
 */

import { TableCell, Box, Typography } from '@mui/material';
import PlayArrow from '@mui/icons-material/PlayArrow';
import Pause from '@mui/icons-material/Pause';
import { PlayIcon } from '@/components/library/Styles/Table.styles';
import { tokens } from '@/design-system';

interface TrackPlayIndicatorProps {
  isCurrentTrack: boolean;
  isPlaying: boolean;
  trackNumber?: number;
  index: number;
}

export const TrackPlayIndicator = ({
  isCurrentTrack,
  isPlaying,
  trackNumber,
  index,
}: TrackPlayIndicatorProps) => {
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
                fontSize: tokens.typography.fontSize.base,
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
