
import { Table, TableBody, TableRow, TableCell, Typography } from '@mui/material';
import { TracksTableContainer } from '@/components/library/Styles/ArtistDetail.styles';
import { usePlaybackState } from '@/components/library/usePlaybackState';
import TracksTableHeader from './TracksTableHeader';
import ArtistTrackRow from './ArtistTrackRow';
import useDurationFormatter from './useDurationFormatter';
import type { DetailTrack as Track } from '@/types/domain';

interface TracksTabProps {
  tracks: Track[];
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
export const TracksTab = ({
  tracks,
  onTrackClick,
}: TracksTabProps) => {
  const { formatDuration } = useDurationFormatter();
  // Read playback state from Redux directly instead of prop-drilling (#4154).
  const { currentTrackId, isPlaying } = usePlaybackState();

  if (!tracks || tracks.length === 0) {
    return (
      <TableRow>
        <TableCell colSpan={4} align="center" sx={{ py: 4 }}>
          <Typography sx={{
            color: "text.secondary"
          }}>
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
