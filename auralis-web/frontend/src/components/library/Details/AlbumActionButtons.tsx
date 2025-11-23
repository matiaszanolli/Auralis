/**
 * AlbumActionButtons - Action buttons for album header (play, favorite, queue, more)
 *
 * Shows interactive controls for album playback and actions.
 */

import React from 'react';
import { Box, IconButton, Tooltip } from '@mui/material';
import {
  PlayArrow,
  Pause,
  AddToQueue,
  MoreVert,
  Favorite,
  FavoriteBorder,
} from '@mui/icons-material';
import { PlayButton } from '../Styles/Button.styles';
import { auroraOpacity } from '../Styles/Color.styles';
import { tokens } from '@/design-system/tokens';

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
    <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
      <PlayButton
        startIcon={isPlaying && firstTrackId ? <Pause /> : <PlayArrow />}
        onClick={onPlay}
      >
        {isPlaying && firstTrackId ? 'Pause' : 'Play Album'}
      </PlayButton>

      <Tooltip title={isFavorite ? 'Remove from favorites' : 'Add to favorites'}>
        <IconButton
          onClick={onToggleFavorite}
          disabled={savingFavorite}
          sx={{
            color: isFavorite ? tokens.colors.accent.error : 'text.secondary',
            '&:hover': {
              backgroundColor: auroraOpacity.ultraLight,
            },
            '&:disabled': {
              opacity: 0.6,
              cursor: 'not-allowed',
            },
          }}
        >
          {isFavorite ? <Favorite /> : <FavoriteBorder />}
        </IconButton>
      </Tooltip>

      <Tooltip title="Add to queue">
        <IconButton
          onClick={onAddToQueue}
          sx={{
            '&:hover': {
              backgroundColor: auroraOpacity.ultraLight,
            },
          }}
        >
          <AddToQueue />
        </IconButton>
      </Tooltip>

      <Tooltip title="More options">
        <IconButton
          onClick={onMoreOptions}
          sx={{
            '&:hover': {
              backgroundColor: auroraOpacity.ultraLight,
            },
          }}
        >
          <MoreVert />
        </IconButton>
      </Tooltip>
    </Box>
  );
};
