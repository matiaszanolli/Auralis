import { MouseEvent } from 'react';
import { Box } from '@mui/material';
import {
  StyledListItem,
  StyledListItemButton,
  ArtistName,
  ArtistInfo
} from '@/components/library/Styles/ArtistList.styles';
import type { Artist } from '@/types/domain';

interface ArtistListItemProps {
  artist: Artist;
  onClick: (artist: Artist) => void;
  onContextMenu: (e: MouseEvent, artist: Artist) => void;
}

/**
 * ArtistListItem - Glass card for artist display
 *
 * Displays:
 * - Artist name (primary typography)
 * - Album and track count metadata
 * - Glass card with hover effects for starfield visibility
 */
export const ArtistListItem = ({
  artist,
  onClick,
  onContextMenu
}: ArtistListItemProps) => {
  // Expose the album/track counts to screen readers, matching what sighted
  // users see in ArtistInfo (#4207).
  const albumLabel = artist.albumCount
    ? `${artist.albumCount} ${artist.albumCount === 1 ? 'album' : 'albums'}`
    : '';
  const trackLabel = artist.trackCount
    ? `${artist.trackCount} ${artist.trackCount === 1 ? 'track' : 'tracks'}`
    : '';
  const ariaLabel = [artist.name, albumLabel, trackLabel]
    .filter(Boolean)
    .join(', ');

  return (
    <StyledListItem>
      <StyledListItemButton
        aria-label={ariaLabel}
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
