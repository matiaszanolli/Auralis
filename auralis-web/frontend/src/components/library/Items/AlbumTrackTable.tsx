/**
 * AlbumTrackTable - Track listing for album detail view
 *
 * Extracted from AlbumDetailView to reduce component size
 * and improve maintainability. Handles track table rendering
 * with play indicators, duration formatting, and click handlers.
 */

import React from 'react';
import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Typography,
  Box
} from '@mui/material';
import { PlayArrow, Pause } from '@mui/icons-material';
import { StyledTableRow, PlayIcon } from '../Styles/Table.styles';
import { tokens } from '@/design-system/tokens';

interface Track {
  id: number;
  title: string;
  artist: string;
  duration: number;
  track_number?: number;
  disc_number?: number;
}

interface AlbumTrackTableProps {
  tracks: Track[];
  currentTrackId?: number;
  isPlaying?: boolean;
  onTrackClick: (track: Track) => void;
  formatDuration: (seconds: number) => string;
}

export const AlbumTrackTable: React.FC<AlbumTrackTableProps> = ({
  tracks,
  currentTrackId,
  isPlaying = false,
  onTrackClick,
  formatDuration
}) => {
  return (
    <TableContainer
      component={Paper}
      elevation={2}
      sx={{
        background: 'rgba(255,255,255,0.03)',
        borderRadius: 2,
        backdropFilter: 'blur(10px)'
      }}
    >
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
              Artist
            </TableCell>
            <TableCell align="right" width="100px" sx={{ color: 'text.secondary', fontWeight: 'bold' }}>
              Duration
            </TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {tracks && tracks.length > 0 ? (
            tracks.map((track, index) => (
              <StyledTableRow
                key={track.id}
                onClick={() => onTrackClick(track)}
                className={currentTrackId === track.id ? 'current-track' : ''}
              >
                <TableCell>
                  <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    {currentTrackId === track.id && isPlaying ? (
                      <Pause sx={{ fontSize: 20, color: tokens.colors.accent.purple }} />
                    ) : (
                      <>
                        <Typography
                          className="track-number"
                          sx={{
                            fontSize: '0.9rem',
                            color: 'text.secondary',
                            '.current-track &': { display: 'none' }
                          }}
                        >
                          {track.track_number || index + 1}
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
                    {track.artist}
                  </Typography>
                </TableCell>
                <TableCell align="right">
                  <Typography sx={{ fontSize: '0.9rem', color: 'text.secondary' }}>
                    {formatDuration(track.duration)}
                  </Typography>
                </TableCell>
              </StyledTableRow>
            ))
          ) : (
            <TableRow>
              <TableCell colSpan={4} align="center" sx={{ py: 4 }}>
                <Typography color="text.secondary">
                  No tracks found for this album
                </Typography>
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </TableContainer>
  );
};

export default AlbumTrackTable;
