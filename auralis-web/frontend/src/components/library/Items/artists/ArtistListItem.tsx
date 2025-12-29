import React from 'react';
import { Box } from '@mui/material';
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
 * ArtistListItem - Glass card for artist display
 *
 * Displays:
 * - Artist name (primary typography)
 * - Album and track count metadata
 * - Glass card with hover effects for starfield visibility
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
        <Box sx={{ display: 'flex', flexDirection: 'column', flex: 1 }}>
          <ArtistName className="artist-name">
            {artist.name}
          </ArtistName>
          <ArtistInfo>
            {artist.albumCount
              ? `${artist.albumCount} ${artist.albumCount === 1 ? 'album' : 'albums'}`
              : ''}
            {artist.albumCount && artist.trackCount ? ' • ' : ''}
            {artist.trackCount
              ? `${artist.trackCount} ${artist.trackCount === 1 ? 'track' : 'tracks'}`
              : ''}
          </ArtistInfo>
        </Box>
      </StyledListItemButton>
    </StyledListItem>
  );
};

export default ArtistListItem;
