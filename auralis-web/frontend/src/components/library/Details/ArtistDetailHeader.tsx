/**
 * ArtistDetailHeader Component
 *
 * Header section with back button and artist info
 */

import { tokens } from '@/design-system';
import ArrowBack from '@mui/icons-material/ArrowBack';
import ArtistHeader from './ArtistHeader';
import { type Artist } from './useArtistDetailsData';
import { IconButton } from '@/design-system';
import { themeVars } from '@/theme/semanticTheme';

interface ArtistDetailHeaderProps {
  artist: Artist;
  onBack?: () => void;
  onPlayAll: () => void;
  onShuffle: () => void;
}

export const ArtistDetailHeaderSection = ({
  artist,
  onBack,
  onPlayAll,
  onShuffle,
}: ArtistDetailHeaderProps) => {
  return (
    <>
      {onBack && (
        <IconButton
          onClick={onBack}
          aria-label="Go back to artists library"
          sx={{
            mb: tokens.spacing.lg,
            color: themeVars.textSecondary,
            border: `1px solid ${tokens.colors.border.light}`,
            borderRadius: tokens.borderRadius.md,
            padding: tokens.spacing.sm,
            transition: tokens.transitions.all,
            '&:hover': {
              backgroundColor: themeVars.surfaceSecondary,
              borderColor: tokens.colors.accent.primary,
              transform: 'scale(1.05)',
            },
            '&:focus-visible': {
              outline: `3px solid ${tokens.colors.accent.primary}`,
              outlineOffset: '2px',
            },
          }}
        >
          <ArrowBack />
        </IconButton>
      )}

      <ArtistHeader
        artist={artist}
        onPlayAll={onPlayAll}
        onShuffle={onShuffle}
      />
    </>
  );
};
