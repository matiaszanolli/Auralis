/**
 * ArtistTrackRow - Individual track row in artist tracks table
 */

import React from 'react';
import { TableCell, Typography, Box } from '@mui/material';
import { PlayArrow, Pause } from '@mui/icons-material';
import { StyledTableRow, PlayIcon } from '../Styles/Table.styles';
import { type Track } from '../Details/useArtistDetailsData';
import { tokens } from '@/design-system';

interface ArtistTrackRowProps {
  track: Track;
  index: number;
  isCurrentTrack: boolean;
  isPlaying: boolean;
  onTrackClick: (track: Track) => void;
  formatDuration: (seconds: number) => string;
}

export const ArtistTrackRow: React.FC<ArtistTrackRowProps> = ({
  track,
  index,
  isCurrentTrack,
  isPlaying,
  onTrackClick,
  formatDuration,
}) => {
  return (
    <StyledTableRow
      onClick={() => onTrackClick(track)}
      className={isCurrentTrack ? 'current-track' : ''}
    >
      <TableCell>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          {isCurrentTrack && isPlaying ? (
            <Pause sx={{ fontSize: 20, color: tokens.colors.accent.primary }} />
          ) : (
            <>
              <Typography
                sx={{
                  fontSize: '0.9rem',
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
            fontSize: '0.95rem',
            fontWeight: isCurrentTrack ? 'bold' : 'normal',
          }}
        >
          {track.title}
        </Typography>
      </TableCell>
      <TableCell>
        <Typography sx={{ fontSize: '0.9rem', color: 'text.secondary' }}>
          {track.album}
        </Typography>
      </TableCell>
      <TableCell align="right">
        <Typography sx={{ fontSize: '0.9rem', color: 'text.secondary' }}>
          {formatDuration(track.duration)}
        </Typography>
      </TableCell>
    </StyledTableRow>
  );
};

export default ArtistTrackRow;
