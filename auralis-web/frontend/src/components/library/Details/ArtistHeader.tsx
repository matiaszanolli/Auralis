import React from 'react';

import {
  PlayArrow,
  Shuffle,
  MoreVert
} from '@mui/icons-material';
import { tokens } from '@/design-system';
import DetailViewHeader from './DetailViewHeader';
import { ArtistAvatarCircle } from '../Styles/ArtistDetail.styles';
import { IconButton, Button } from '@/design-system';
import { Box, Typography } from '@mui/material';
import type { Artist } from '@/types/domain';

interface ArtistHeaderProps {
  artist: Artist;
  onPlayAll: () => void;
  onShuffle: () => void;
}

/**
 * ArtistHeader - Artist detail view header with artwork, stats, and actions
 *
 * Displays:
 * - Artist avatar (first letter)
 * - Artist name as title
 * - Album and track counts as metadata
 * - Play All and Shuffle buttons
 * - More options menu button
 */
export const ArtistHeader: React.FC<ArtistHeaderProps> = ({
  artist,
  onPlayAll,
  onShuffle
}) => {
  const getArtistInitial = (name: string): string => {
    return name.charAt(0).toUpperCase();
  };

  return (
    <DetailViewHeader
      artwork={
        artist.artworkUrl ? (
          // Real artist image (Phase 2)
          <Box
            component="img"
            src={artist.artworkUrl}
            alt={artist.name}
            sx={{
              width: 200,
              height: 200,
              borderRadius: '50%',
              objectFit: 'cover',
              border: `2px solid ${tokens.colors.border.light}`,
              boxShadow: tokens.shadows.md,
            }}
            onError={(e) => {
              // Fallback to placeholder on image load error
              e.currentTarget.style.display = 'none';
            }}
          />
        ) : (
          // Fallback to placeholder
          <ArtistAvatarCircle>
            {getArtistInitial(artist.name)}
          </ArtistAvatarCircle>
        )
      }
      title={artist.name}
      metadata={
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: tokens.spacing.xs }}>
          {/* Primary stats line */}
          <Typography variant="body1" sx={{
            color: tokens.colors.text.secondary,
            fontSize: tokens.typography.fontSize.md,
            fontWeight: tokens.typography.fontWeight.medium,
            letterSpacing: '0.02em',
          }}>
            {artist.albumCount && `${artist.albumCount} ${artist.albumCount === 1 ? 'Album' : 'Albums'}`}
            {artist.albumCount && artist.trackCount && ' • '}
            {artist.trackCount && `${artist.trackCount} ${artist.trackCount === 1 ? 'Track' : 'Tracks'}`}
          </Typography>

          {/* Additional context - currently placeholder, can be expanded with backend data */}
          <Typography variant="body2" sx={{
            color: tokens.colors.text.tertiary,
            fontSize: tokens.typography.fontSize.sm,
            fontWeight: tokens.typography.fontWeight.normal,
          }}>
            Artist
          </Typography>
        </Box>
      }
      actions={
        <Box sx={{ display: 'flex', gap: tokens.spacing.md, flexWrap: 'wrap', alignItems: 'center' }}>
          {/* Play All Button */}
          <Button
            variant="primary"
            startIcon={<PlayArrow />}
            onClick={onPlayAll}
            sx={{
              background: tokens.gradients.aurora,
              color: tokens.colors.text.primary,
              fontWeight: tokens.typography.fontWeight.semibold,
              padding: `${tokens.spacing.sm} ${tokens.spacing.lg}`,
              borderRadius: tokens.borderRadius.md,
              border: 'none',
              cursor: 'pointer',
              transition: tokens.transitions.all,
              boxShadow: tokens.shadows.md,
              outline: 'none',
              '&:hover': {
                transform: 'translateY(-2px)',
                boxShadow: tokens.shadows.glowMd,
              },
              '&:active': {
                transform: 'translateY(0)',
              },
            }}
          >
            Play All
          </Button>

          {/* Shuffle Button */}
          <Button
            variant="secondary"
            startIcon={<Shuffle />}
            onClick={onShuffle}
            sx={{
              color: tokens.colors.text.secondary,
              borderColor: tokens.colors.border.light,
              fontWeight: tokens.typography.fontWeight.semibold,
              padding: `${tokens.spacing.sm} ${tokens.spacing.lg}`,
              borderRadius: tokens.borderRadius.md,
              transition: tokens.transitions.all,
              '&:hover': {
                backgroundColor: tokens.colors.bg.tertiary,
                borderColor: tokens.colors.accent.primary,
                transform: 'scale(1.05)',
              },
              '&:active': {
                transform: 'scale(0.98)',
              },
            }}
          >
            Shuffle
          </Button>

          {/* More Options Button */}
          <IconButton
            sx={{
              color: tokens.colors.text.secondary,
              border: `1px solid ${tokens.colors.border.light}`,
              borderRadius: tokens.borderRadius.md,
              padding: tokens.spacing.sm,
              transition: tokens.transitions.all,
              '&:hover': {
                backgroundColor: tokens.colors.bg.tertiary,
                borderColor: tokens.colors.accent.primary,
                transform: 'scale(1.05)',
              },
            }}
          >
            <MoreVert />
          </IconButton>
        </Box>
      }
    />
  );
};

export default ArtistHeader;
