import React from 'react';
import { ListItemText } from '@mui/material';
import {
  StyledListItem,
  StyledListItemButton,
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
 * ArtistListItem - Single artist list item with typography-driven identity
 *
 * Displays:
 * - Artist name (primary typography)
 * - Album and track count metadata
 * - Clickable row with context menu support
 */
export const ArtistListItem: React.FC<ArtistListItemProps> = ({
  artist,
  onClick,
  onContextMenu
}) => {
  return (
    <StyledListItem>
      <StyledListItemButton
        onClick={() => onClick(artist)}
        onContextMenu={(e) => onContextMenu(e, artist)}
      >
        <ListItemText
          primary={
            <ArtistName className="artist-name" component="span">
              {artist.name}
            </ArtistName>
          }
          secondary={
            <ArtistInfo component="span">
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
