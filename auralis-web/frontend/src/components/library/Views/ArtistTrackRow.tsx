/**
 * ArtistTrackRow - Individual track row in artist tracks table
 */

import { KeyboardEvent } from 'react';
import { TableCell, Typography, Box } from '@mui/material';
import PlayArrow from '@mui/icons-material/PlayArrow';
import Pause from '@mui/icons-material/Pause';
import { StyledTableRow, PlayIcon } from '@/components/library/Styles/Table.styles';
import type { DetailTrack as Track } from '@/types/domain';
import { tokens } from '@/design-system';

interface ArtistTrackRowProps {
  track: Track;
  index: number;
  isCurrentTrack: boolean;
  isPlaying: boolean;
  onTrackClick: (track: Track) => void;
  formatDuration: (seconds: number) => string;
}

export const ArtistTrackRow = ({
  track,
  index,
  isCurrentTrack,
  isPlaying,
  onTrackClick,
  formatDuration,
}: ArtistTrackRowProps) => {
  return (
    <StyledTableRow
      onClick={() => onTrackClick(track)}
      className={isCurrentTrack ? 'current-track' : ''}
      tabIndex={0}
      aria-label={`Play ${track.title}`}
      onKeyDown={(e: KeyboardEvent) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onTrackClick(track);
        }
      }}
    >
      <TableCell>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          {isCurrentTrack && isPlaying ? (
            <Pause sx={{ fontSize: 20, color: tokens.colors.accent.primary }} />
          ) : (
            <>
              <Typography
                sx={{
                  fontSize: tokens.typography.fontSize.base,
                  color: 'text.secondary',
                  '.current-track &': { display: 'none' },
                }}
              >
                {index + 1}
              </Typography>
              <PlayIcon className="play-icon">
                <PlayArrow sx={{ fontSize: 20 }} />
              </PlayIcon>
            </>
          )}
        </Box>
      </TableCell>
      <TableCell>
        <Typography
          className="track-title"
          sx={{
            fontSize: tokens.typography.fontSize.base,
            fontWeight: isCurrentTrack ? 'bold' : 'normal',
          }}
        >
          {track.title}
        </Typography>
      </TableCell>
      <TableCell>
        <Typography sx={{ fontSize: tokens.typography.fontSize.base, color: 'text.secondary' }}>
          {track.album}
        </Typography>
      </TableCell>
      <TableCell align="right">
        <Typography sx={{ fontSize: tokens.typography.fontSize.base, color: 'text.secondary' }}>
          {formatDuration(track.duration)}
        </Typography>
      </TableCell>
    </StyledTableRow>
  );
};

export default ArtistTrackRow;
