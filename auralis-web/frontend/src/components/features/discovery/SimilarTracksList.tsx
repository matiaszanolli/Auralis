import React from 'react';
import { Box, List } from '@mui/material';
import { SimilarTrack } from '../../../services/similarityService';
import SimilarTracksListItem from './SimilarTracksListItem';
import SimilarTracksHeader from './SimilarTracksHeader';
import SimilarTracksFooter from './SimilarTracksFooter';

interface SimilarTracksListProps {
  tracks: SimilarTrack[];
  useGraph: boolean;
  onTrackSelect: (trackId: number) => void;
  getSimilarityColor: (score: number) => string;
  formatDuration: (seconds?: number) => string;
}

/**
 * SimilarTracksList - Full list with header, items, and footer
 */
export const SimilarTracksList: React.FC<SimilarTracksListProps> = ({
  tracks,
  useGraph,
  onTrackSelect,
  getSimilarityColor,
  formatDuration,
}) => {
  const handleTrackClick = (track: SimilarTrack) => {
    onTrackSelect(track.track_id);
  };

  return (
    <Box>
      {/* Header */}
      <SimilarTracksHeader />

      {/* Tracks List */}
      <List sx={{ p: 0 }}>
        {tracks.map((track, index) => (
          <SimilarTracksListItem
            key={track.track_id}
            track={track}
            index={index}
            totalCount={tracks.length}
            onClick={handleTrackClick}
            getSimilarityColor={getSimilarityColor}
            formatDuration={formatDuration}
          />
        ))}
      </List>

      {/* Footer Info */}
      <SimilarTracksFooter useGraph={useGraph} tracksCount={tracks.length} />
    </Box>
  );
};

export default SimilarTracksList;
