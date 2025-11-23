import React from 'react';
import { MusicNote } from '@mui/icons-material';
import { AlbumArtThumbnail } from '../Styles/TrackRow.styles';

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
export const TrackRowAlbumArt: React.FC<TrackRowAlbumArtProps> = ({
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

export default TrackRowAlbumArt;
