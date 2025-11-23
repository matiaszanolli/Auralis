/**
 * TrackTableRowItem - Individual track row in album table
 */

import React from 'react';
import { TableCell, Typography } from '@mui/material';
import { StyledTableRow } from '../Styles/Table.styles';
import { TrackPlayIndicator } from './TrackPlayIndicator';

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
            fontSize: '0.95rem',
            fontWeight: isCurrentTrack ? 'bold' : 'normal',
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
  );
};

export default TrackTableRowItem;
