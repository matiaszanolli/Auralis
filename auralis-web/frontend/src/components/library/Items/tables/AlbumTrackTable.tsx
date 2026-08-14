/**
 * AlbumTrackTable - Track listing for album detail view
 *
 * Extracted from AlbumDetailView to reduce component size
 * and improve maintainability. Handles track table rendering
 * with play indicators, duration formatting, and click handlers.
 */

import { Table, TableBody, TableContainer, TableRow, Paper, Typography, TableCell } from '@mui/material';
import { tokens } from '@/design-system';
import { themeVars } from '@/theme/semanticTheme';
import { usePlaybackState } from '@/components/library/usePlaybackState';
import TrackTableHeader from './TrackTableHeader';
import TrackTableRowItem from './TrackTableRowItem';

import type { DetailTrack as Track } from '@/types/domain';

interface AlbumTrackTableProps {
  tracks: Track[];
  onTrackClick: (track: Track) => void;
  onFindSimilar?: (trackId: number) => void; // Phase 5: Find similar tracks
  formatDuration: (seconds: number) => string;
}

export const AlbumTrackTable = ({
  tracks,
  onTrackClick,
  onFindSimilar,
  formatDuration
}: AlbumTrackTableProps) => {
  // Read playback state from Redux directly instead of prop-drilling it through
  // the detail-view chain (#4154).
  const { currentTrackId, isPlaying } = usePlaybackState();
  return (
    <TableContainer
      component={Paper}
      sx={{
        // #4464/#4877: was a manual rgba() built by slicing themeVars.surfaceSecondary's
        // hex digits — a dark-only computation that broke under light mode, the
        // same defect #4877 fixed in TrackTableHeader. color-mix() applies the
        // alpha to whichever theme-aware surface is active instead.
        background: `color-mix(in srgb, ${themeVars.surfaceSecondary} 92%, transparent)`,
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
                  color: themeVars.textMuted,
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
