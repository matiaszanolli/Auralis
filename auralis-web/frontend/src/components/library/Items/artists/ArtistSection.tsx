import { MouseEvent, memo } from 'react';
import { Box } from '@mui/material';
import { List } from '@/design-system';
import { AlphabetDivider } from '@/components/library/Styles/ArtistList.styles';
import { ArtistListItem } from './ArtistListItem';
import type { Artist } from '@/types/domain';

interface ArtistSectionProps {
  letter: string;
  artists: Artist[];
  onArtistClick: (artist: Artist) => void;
  onContextMenu: (e: MouseEvent, artist: Artist) => void;
}

/**
 * ArtistSection - Alphabetic section with letter header and grouped artists
 *
 * #3607: wrapped in memo so a context-menu state change on the parent
 * doesn't re-render every letter section + every artist row. Callers must
 * pass stable callback identities (see ArtistListContent's useCallback wrappers).
 */
export const ArtistSection = memo(function ArtistSection({
  letter,
  artists,
  onArtistClick,
  onContextMenu,
}: ArtistSectionProps) {
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
});

export default ArtistSection;
