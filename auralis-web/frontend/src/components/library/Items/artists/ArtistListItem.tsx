import React from 'react';
import { ListItemText } from '@mui/material';
import {
  StyledListItem,
  StyledListItemButton,
  ArtistAvatar,
  ArtistName,
  ArtistInfo
} from '../../Styles/ArtistList.styles';
import type { Artist } from '@/types/domain';

interface ArtistListItemProps {
  artist: Artist;
  onClick: (artist: Artist) => void;
  onContextMenu: (e: React.MouseEvent, artist: Artist) => void;
}

/**
 * ArtistListItem - Single artist list item with avatar and metadata
 *
 * Displays:
 * - Artist avatar with initial
 * - Artist name
 * - Album and track count metadata
 * - Clickable row with context menu support
 */
export const ArtistListItem: React.FC<ArtistListItemProps> = ({
  artist,
  onClick,
  onContextMenu
}) => {
  const getArtistInitial = (name: string): string => {
    return name.charAt(0).toUpperCase();
  };

  return (
    <StyledListItem>
      <StyledListItemButton
        onClick={() => onClick(artist)}
        onContextMenu={(e) => onContextMenu(e, artist)}
      >
        <ArtistAvatar>
          {getArtistInitial(artist.name)}
        </ArtistAvatar>
        <ListItemText
          primary={
            <ArtistName className="artist-name">
              {artist.name}
            </ArtistName>
          }
          secondary={
            <ArtistInfo>
              {artist.albumCount
                ? `${artist.albumCount} ${artist.albumCount === 1 ? 'album' : 'albums'}`
                : ''}
              {artist.albumCount && artist.trackCount ? ' • ' : ''}
              {artist.trackCount
                ? `${artist.trackCount} ${artist.trackCount === 1 ? 'track' : 'tracks'}`
                : ''}
            </ArtistInfo>
          }
        />
      </StyledListItemButton>
    </StyledListItem>
  );
};

export default ArtistListItem;
