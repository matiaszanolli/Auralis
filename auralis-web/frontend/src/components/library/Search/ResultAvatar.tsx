import React from 'react';
import {
  Album as AlbumIcon,
  Person as PersonIcon,
  MusicNote as MusicNoteIcon
} from '@mui/icons-material';
import {
  ArtistSearchAvatar,
  DefaultSearchAvatar
} from '../Styles/SearchStyles.styles';
import AlbumArt from '../album/AlbumArt';

interface SearchResult {
  type: 'track' | 'album' | 'artist';
  id: number;
  title: string;
  subtitle?: string;
  albumId?: number;
}

interface ResultAvatarProps {
  result: SearchResult;
}

/**
 * ResultAvatar - Renders appropriate avatar for search result
 *
 * Returns:
 * - AlbumArt for albums and tracks with album artwork
 * - Artist avatar (first letter) for artists
 * - Default icon avatars for fallbacks
 *
 * Type-specific avatar rendering logic
 */
export const ResultAvatar: React.FC<ResultAvatarProps> = ({ result }) => {
  // Album or track with album artwork
  if (result.type === 'album' || (result.type === 'track' && result.albumId)) {
    return (
      <AlbumArt
        albumId={result.albumId || result.id}
        size={40}
        borderRadius={4}
      />
    );
  }

  // Artist - first letter avatar
  if (result.type === 'artist') {
    return (
      <ArtistSearchAvatar>
        {result.title.charAt(0).toUpperCase()}
      </ArtistSearchAvatar>
    );
  }

  // Default icon-based avatars
  const getIcon = () => {
    switch (result.type) {
      case 'track':
        return <MusicNoteIcon />;
      case 'album':
        return <AlbumIcon />;
      case 'artist':
        return <PersonIcon />;
      default:
        return <MusicNoteIcon />;
    }
  };

  return (
    <DefaultSearchAvatar>
      {getIcon()}
    </DefaultSearchAvatar>
  );
};

export default ResultAvatar;
