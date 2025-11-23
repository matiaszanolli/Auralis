/**
 * AlbumTrackTable - Track listing for album detail view
 *
 * Extracted from AlbumDetailView to reduce component size
 * and improve maintainability. Handles track table rendering
 * with play indicators, duration formatting, and click handlers.
 */

import React from 'react';
import { Table, TableBody, TableContainer, TableRow, Paper, Typography, TableCell } from '@mui/material';
import TrackTableHeader from './TrackTableHeader';
import TrackTableRowItem from './TrackTableRowItem';

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
        <TrackTableHeader />
        <TableBody>
          {tracks && tracks.length > 0 ? (
            tracks.map((track, index) => (
              <TrackTableRowItem
                key={track.id}
                track={track}
                index={index}
                isCurrentTrack={currentTrackId === track.id}
                isPlaying={isPlaying}
                onTrackClick={onTrackClick}
                formatDuration={formatDuration}
              />
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
