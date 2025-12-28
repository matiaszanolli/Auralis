/**
 * AlbumTrackTable - Track listing for album detail view
 *
 * Extracted from AlbumDetailView to reduce component size
 * and improve maintainability. Handles track table rendering
 * with play indicators, duration formatting, and click handlers.
 */

import React from 'react';
import { Table, TableBody, TableContainer, TableRow, Paper, Typography, TableCell } from '@mui/material';
import { tokens } from '@/design-system';
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
  onFindSimilar?: (trackId: number) => void; // Phase 5: Find similar tracks
  formatDuration: (seconds: number) => string;
}

export const AlbumTrackTable: React.FC<AlbumTrackTableProps> = ({
  tracks,
  currentTrackId,
  isPlaying = false,
  onTrackClick,
  onFindSimilar,
  formatDuration
}) => {
  return (
    <TableContainer
      component={Paper}
      sx={{
        background: `rgba(${parseInt(tokens.colors.bg.level2.slice(1, 3), 16)}, ${parseInt(tokens.colors.bg.level2.slice(3, 5), 16)}, ${parseInt(tokens.colors.bg.level2.slice(5, 7), 16)}, 0.92)`,
        borderRadius: tokens.borderRadius.lg,
        backdropFilter: 'blur(12px)',
        border: `1px solid ${tokens.colors.border.light}`,
        boxShadow: tokens.shadows.md,
        overflow: 'hidden',
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
                onFindSimilar={onFindSimilar}
                formatDuration={formatDuration}
              />
            ))
          ) : (
            <TableRow>
              <TableCell colSpan={4} align="center" sx={{
                py: tokens.spacing.xl,
                borderTop: `1px solid ${tokens.colors.border.light}`,
              }}>
                <Typography sx={{
                  color: tokens.colors.text.tertiary,
                  fontSize: tokens.typography.fontSize.md,
                }}>
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
