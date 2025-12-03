/**
 * ArtistDetailHeader Component
 *
 * Header section with back button and artist info
 */

import React from 'react';

import { tokens } from '@/design-system';
import { ArrowBack } from '@mui/icons-material';
import ArtistHeader from './ArtistHeader';
import { type Track, type Album, type Artist } from './useArtistDetailsData';
import { Button, IconButton } from '@/design-system';
import { Box, Container } from '@mui/material';

interface ArtistDetailHeaderProps {
  artist: Artist;
  onBack?: () => void;
  onPlayAll: () => void;
  onShuffle: () => void;
}

export const ArtistDetailHeaderSection: React.FC<ArtistDetailHeaderProps> = ({
  artist,
  onBack,
  onPlayAll,
  onShuffle,
}) => {
  return (
    <>
      {onBack && (
        <IconButton
          onClick={onBack}
          aria-label="Go back to artists library"
          sx={{
            mb: tokens.spacing.lg,
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
