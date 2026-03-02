import React from 'react';
import { Box } from '@mui/material';
import { List } from '@/design-system';
import { AlphabetDivider } from '../../Styles/ArtistList.styles';
import { ArtistListItem } from './ArtistListItem';
import type { Artist } from '@/types/domain';

interface ArtistSectionProps {
  letter: string;
  artists: Artist[];
  onArtistClick: (artist: Artist) => void;
  onContextMenu: (e: React.MouseEvent, artist: Artist) => void;
}

/**
 * ArtistSection - Alphabetic section with letter header and grouped artists
 *
 * Displays:
 * - Letter header divider
 * - All artists starting with that letter
 * - Uses ArtistListItem for each artist
 */
export const ArtistSection: React.FC<ArtistSectionProps> = ({
  letter,
  artists,
  onArtistClick,
  onContextMenu
}) => {
  return (
    <Box>
      <AlphabetDivider>{letter}</AlphabetDivider>
      <List>
        {artists.map((artist) => (
          <ArtistListItem
            key={artist.id}
            artist={artist}
            onClick={onArtistClick}
            onContextMenu={onContextMenu}
          />
        ))}
      </List>
    </Box>
  );
};

export default ArtistSection;
