import React from 'react';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
  Box
} from '@mui/material';
import {
  PlayArrow,
  Pause
} from '@mui/icons-material';
import { StyledTableRow, PlayIcon } from './Table.styles';
import { TracksTableContainer } from './ArtistDetail.styles';

interface Track {
  id: number;
  title: string;
  album: string;
  duration: number;
  track_number?: number;
}

interface TracksTabProps {
  tracks: Track[];
  currentTrackId?: number;
  isPlaying?: boolean;
  onTrackClick: (track: Track) => void;
}

/**
 * TracksTab - Table of all tracks for artist detail view
 *
 * Displays:
 * - Track number/play indicator
 * - Track title (bold if current)
 * - Album name
 * - Duration in MM:SS format
 * - Empty state message
 */
export const TracksTab: React.FC<TracksTabProps> = ({
  tracks,
  currentTrackId,
  isPlaying = false,
  onTrackClick
}) => {
  const formatDuration = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  if (!tracks || tracks.length === 0) {
    return (
      <TableRow>
        <TableCell colSpan={4} align="center" sx={{ py: 4 }}>
          <Typography color="text.secondary">
            No tracks found for this artist
          </Typography>
        </TableCell>
      </TableRow>
    );
  }

  return (
    <TracksTableContainer>
      <Table>
        <TableHead>
          <TableRow>
            <TableCell width="60px" sx={{ color: 'text.secondary', fontWeight: 'bold' }}>
              #
            </TableCell>
            <TableCell sx={{ color: 'text.secondary', fontWeight: 'bold' }}>
              Title
            </TableCell>
            <TableCell sx={{ color: 'text.secondary', fontWeight: 'bold' }}>
              Album
            </TableCell>
            <TableCell align="right" width="100px" sx={{ color: 'text.secondary', fontWeight: 'bold' }}>
              Duration
            </TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {tracks.map((track, index) => (
            <StyledTableRow
              key={track.id}
              onClick={() => onTrackClick(track)}
              className={currentTrackId === track.id ? 'current-track' : ''}
            >
              <TableCell>
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  {currentTrackId === track.id && isPlaying ? (
                    <Pause sx={{ fontSize: 20, color: '#667eea' }} />
                  ) : (
                    <>
                      <Typography
                        sx={{
                          fontSize: '0.9rem',
                          color: 'text.secondary',
                          '.current-track &': { display: 'none' }
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
                    fontWeight: currentTrackId === track.id ? 'bold' : 'normal'
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
          ))}
        </TableBody>
      </Table>
    </TracksTableContainer>
  );
};

export default TracksTab;
