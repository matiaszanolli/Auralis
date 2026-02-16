import React from 'react';
import { TrackInfo, TrackTitle, TrackArtist, TrackAlbum, TrackDuration } from './TrackRow.styles';

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
const TrackRowMetadataComponent: React.FC<TrackRowMetadataProps> = ({
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
        <TrackAlbum data-testid="track-album" sx={{ display: { xs: 'none', md: 'block' } }}>
          {album}
        </TrackAlbum>
      )}

      <TrackDuration>{duration}</TrackDuration>
    </>
  );
};

/**
 * Memoized TrackRowMetadata with custom comparator
 * Only re-renders when title, artist, album, duration, or isCurrent change
 */
export const TrackRowMetadata = React.memo<TrackRowMetadataProps>(
  TrackRowMetadataComponent,
  (prev, next) => {
    return (
      prev.title === next.title &&
      prev.artist === next.artist &&
      prev.album === next.album &&
      prev.duration === next.duration &&
      prev.isCurrent === next.isCurrent
    );
  }
);

export default TrackRowMetadata;
