import React from 'react';
import {
  Box,
  Typography,
  IconButton,
  Button
} from '@mui/material';
import {
  PlayArrow,
  Shuffle,
  MoreVert
} from '@mui/icons-material';
import { tokens } from '@/design-system/tokens';
import DetailViewHeader from './DetailViewHeader';
import { ArtistAvatarCircle } from '../Styles/ArtistDetail.styles';

interface Artist {
  id: number;
  name: string;
  album_count?: number;
  track_count?: number;
}

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
        <ArtistAvatarCircle>
          {getArtistInitial(artist.name)}
        </ArtistAvatarCircle>
      }
      title={artist.name}
      metadata={
        <Typography variant="body1" sx={{
          color: tokens.colors.text.tertiary,
          fontSize: tokens.typography.fontSize.sm,
          fontWeight: tokens.typography.fontWeight.regular,
        }}>
          {artist.album_count && `${artist.album_count} ${artist.album_count === 1 ? 'album' : 'albums'}`}
          {artist.album_count && artist.track_count && ' • '}
          {artist.track_count && `${artist.track_count} ${artist.track_count === 1 ? 'track' : 'tracks'}`}
        </Typography>
      }
      actions={
        <Box sx={{ display: 'flex', gap: tokens.spacing.md, flexWrap: 'wrap', alignItems: 'center' }}>
          {/* Play All Button */}
          <Button
            variant="contained"
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
            variant="outlined"
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
