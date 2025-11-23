import React from 'react';
import { TrackInfo, TrackTitle, TrackArtist, TrackAlbum, TrackDuration } from '../Styles/TrackRow.styles';

interface TrackRowMetadataProps {
  title: string;
  artist: string;
  album?: string;
  duration: string;
  isCurrent: boolean;
}

/**
 * TrackRowMetadata - Track title, artist, album, and duration
 *
 * Displays track metadata in a structured layout.
 */
export const TrackRowMetadata: React.FC<TrackRowMetadataProps> = ({
  title,
  artist,
  album,
  duration,
  isCurrent,
}) => {
  const isCurrentStr = isCurrent ? 'true' : 'false';

  return (
    <>
      <TrackInfo>
        <TrackTitle iscurrent={isCurrentStr}>{title}</TrackTitle>
        <TrackArtist>{artist}</TrackArtist>
      </TrackInfo>

      {album && (
        <TrackAlbum sx={{ display: { xs: 'none', md: 'block' } }}>
          {album}
        </TrackAlbum>
      )}

      <TrackDuration>{duration}</TrackDuration>
    </>
  );
};

export default TrackRowMetadata;
