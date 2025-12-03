/**
 * AlbumActionButtons - Action buttons for album header (play, favorite, queue, more)
 *
 * Shows interactive controls for album playback and actions.
 */

import React from 'react';

import {
  PlayArrow,
  Pause,
  AddToQueue,
  MoreVert,
  Favorite,
  FavoriteBorder,
} from '@mui/icons-material';
import { Tooltip, tokens } from '@/design-system';
import { IconButton, Button } from '@/design-system';
import { Box } from '@mui/material';

interface AlbumActionButtonsProps {
  isPlaying: boolean;
  isFavorite: boolean;
  savingFavorite: boolean;
  firstTrackId?: number;
  albumId?: number;
  onPlay: () => void;
  onToggleFavorite: () => void;
  onAddToQueue?: () => void;
  onMoreOptions?: () => void;
}

export const AlbumActionButtons: React.FC<AlbumActionButtonsProps> = ({
  isPlaying,
  isFavorite,
  savingFavorite,
  firstTrackId,
  albumId,
  onPlay,
  onToggleFavorite,
  onAddToQueue,
  onMoreOptions,
}) => {
  return (
    <Box sx={{ display: 'flex', gap: tokens.spacing.md, flexWrap: 'wrap', alignItems: 'center' }}>
      {/* Primary Play/Pause Button */}
      <Button
        variant="contained"
        startIcon={isPlaying && firstTrackId ? <Pause /> : <PlayArrow />}
        onClick={onPlay}
        disabled={savingFavorite}
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
          '&:disabled': {
            opacity: 0.5,
            cursor: 'not-allowed',
          },
        }}
      >
        {isPlaying && firstTrackId ? 'Pause' : 'Play Album'}
      </Button>

      {/* Favorite Button */}
      <Tooltip title={isFavorite ? 'Remove from favorites' : 'Add to favorites'}>
        <IconButton
          onClick={onToggleFavorite}
          disabled={savingFavorite}
          aria-pressed={isFavorite}
          aria-label={isFavorite ? 'Album is favorited. Press to remove' : 'Album is not favorited. Press to add'}
          sx={{
            color: isFavorite ? tokens.colors.semantic.error : tokens.colors.text.secondary,
            border: `1px solid ${tokens.colors.border.light}`,
            borderRadius: tokens.borderRadius.md,
            padding: tokens.spacing.sm,
            transition: tokens.transitions.all,
            '&:hover': {
              backgroundColor: tokens.colors.bg.tertiary,
              borderColor: tokens.colors.accent.primary,
              transform: 'scale(1.05)',
            },
            '&:disabled': {
              opacity: 0.5,
              cursor: 'not-allowed',
            },
          }}
        >
          {isFavorite ? <Favorite /> : <FavoriteBorder />}
        </IconButton>
      </Tooltip>

      {/* Add to Queue Button */}
      <Tooltip title="Add to queue">
        <IconButton
          onClick={onAddToQueue}
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
          <AddToQueue />
        </IconButton>
      </Tooltip>

      {/* More Options Button */}
      <Tooltip title="More options">
        <IconButton
          onClick={onMoreOptions}
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
      </Tooltip>
    </Box>
  );
};
