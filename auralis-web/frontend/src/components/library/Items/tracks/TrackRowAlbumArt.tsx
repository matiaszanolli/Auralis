import React from 'react';
import { MusicNote } from '@mui/icons-material';
import { AlbumArtThumbnail } from './TrackRow.styles';

interface TrackRowAlbumArtProps {
  albumArt?: string;
  title: string;
  album?: string;
  shouldShowImage: boolean;
  onImageError: () => void;
}

/**
 * TrackRowAlbumArt - Album art thumbnail for track row
 *
 * Shows album art image or fallback music note icon.
 */
const TrackRowAlbumArtComponent: React.FC<TrackRowAlbumArtProps> = ({
  albumArt,
  title,
  album,
  shouldShowImage,
  onImageError,
}) => {
  return (
    <AlbumArtThumbnail>
      {shouldShowImage && albumArt ? (
        <img src={albumArt} alt={album || title} onError={onImageError} />
      ) : (
        <MusicNote sx={{ color: 'rgba(255, 255, 255, 0.3)', fontSize: '20px' }} />
      )}
    </AlbumArtThumbnail>
  );
};

/**
 * Memoized TrackRowAlbumArt with custom comparator
 * Only re-renders when albumArt, title, album, or shouldShowImage change
 * onImageError is excluded as it's recreated on parent render but doesn't affect visual state
 */
export const TrackRowAlbumArt = React.memo<TrackRowAlbumArtProps>(
  TrackRowAlbumArtComponent,
  (prev, next) => {
    return (
      prev.albumArt === next.albumArt &&
      prev.title === next.title &&
      prev.album === next.album &&
      prev.shouldShowImage === next.shouldShowImage
    );
  }
);

export default TrackRowAlbumArt;
