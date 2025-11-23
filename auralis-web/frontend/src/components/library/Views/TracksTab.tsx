import React from 'react';
import { Table, TableBody, TableRow, TableCell, Typography } from '@mui/material';
import { TracksTableContainer } from '../Styles/ArtistDetail.styles';
import TracksTableHeader from './TracksTableHeader';
import ArtistTrackRow from './ArtistTrackRow';
import useDurationFormatter from './useDurationFormatter';

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
  onTrackClick,
}) => {
  const { formatDuration } = useDurationFormatter();

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
        <TracksTableHeader />
        <TableBody>
          {tracks.map((track, index) => (
            <ArtistTrackRow
              key={track.id}
              track={track}
              index={index}
              isCurrentTrack={currentTrackId === track.id}
              isPlaying={isPlaying}
              onTrackClick={onTrackClick}
              formatDuration={formatDuration}
            />
          ))}
        </TableBody>
      </Table>
    </TracksTableContainer>
  );
};

export default TracksTab;
