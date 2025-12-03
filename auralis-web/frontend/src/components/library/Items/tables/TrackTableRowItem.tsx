/**
 * TrackTableRowItem - Individual track row in album table
 */

import React from 'react';
import { TableCell, Typography } from '@mui/material';
import { tokens } from '@/design-system/tokens';
import { StyledTableRow } from '../../Styles/Table.styles';
import { TrackPlayIndicator } from '../tracks/TrackPlayIndicator';

interface Track {
  id: number;
  title: string;
  artist: string;
  duration: number;
  track_number?: number;
  disc_number?: number;
}

interface TrackTableRowItemProps {
  track: Track;
  index: number;
  isCurrentTrack: boolean;
  isPlaying: boolean;
  onTrackClick: (track: Track) => void;
  formatDuration: (seconds: number) => string;
}

export const TrackTableRowItem: React.FC<TrackTableRowItemProps> = ({
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
      <TrackPlayIndicator
        isCurrentTrack={isCurrentTrack}
        isPlaying={isPlaying}
        trackNumber={track.track_number}
        index={index}
      />
      <TableCell>
        <Typography
          className="track-title"
          sx={{
            fontSize: tokens.typography.fontSize.md,
            fontWeight: isCurrentTrack ? tokens.typography.fontWeight.semibold : tokens.typography.fontWeight.normal,
            color: isCurrentTrack ? tokens.colors.accent.primary : tokens.colors.text.primary,
          }}
        >
          {track.title}
        </Typography>
      </TableCell>
      <TableCell>
        <Typography sx={{
          fontSize: tokens.typography.fontSize.sm,
          color: tokens.colors.text.secondary,
        }}>
          {track.artist}
        </Typography>
      </TableCell>
      <TableCell align="right">
        <Typography sx={{
          fontSize: tokens.typography.fontSize.sm,
          color: tokens.colors.text.tertiary,
          fontFamily: tokens.typography.fontFamily.mono,
        }}>
          {formatDuration(track.duration)}
        </Typography>
      </TableCell>
    </StyledTableRow>
  );
};

export default TrackTableRowItem;
