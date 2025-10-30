import React, { useState } from 'react';
import { Card, CardMedia, CardContent, Typography, Box, IconButton, styled, ButtonBase, alpha } from '@mui/material';
import { PlayArrow, MoreVert } from '@mui/icons-material';
import { colors, gradients, shadows, borderRadius, transitions, spacing } from '../../theme/auralisTheme';
import AlbumArt from '../album/AlbumArt';
import { useContextMenu, ContextMenu, getAlbumContextActions } from '../shared/ContextMenu';
import { useToast } from '../shared/Toast';

interface AlbumCardProps {
  id: number;
  title: string;
  artist: string;
  albumId?: number;
  albumArt?: string;
  trackCount?: number;
  onPlay: (id: number) => void;
  onContextMenu?: (id: number, event: React.MouseEvent) => void;
}

const StyledCard = styled(Card)(({ theme }) => ({
  position: 'relative',
  backgroundColor: colors.background.secondary,
  borderRadius: `${borderRadius.sm}px`,
  overflow: 'visible', // Changed to visible for shadow to show properly
  cursor: 'pointer',
  transition: `all ${transitions.normal}`,
  border: `1px solid transparent`,
  willChange: 'transform', // Performance optimization for animations

  '&:hover': {
    transform: 'translateY(-6px)',
    boxShadow: `${shadows.glowPurple}, ${shadows.lg}`,
    border: `1px solid ${alpha('#667eea', 0.4)}`,
    backgroundColor: colors.background.elevated,

    '& .play-overlay': {
      opacity: 1,
    },

    '& .album-title': {
      color: '#667eea',
    },

    '& .more-button': {
      opacity: 1,
    },
  },

  '&:active': {
    transform: 'translateY(-3px)',
    transition: `all ${transitions.fast}`,
  },

  // Focus visible for keyboard navigation
  '&:focus-visible': {
    outline: 'none',
    boxShadow: `0 0 0 3px ${alpha('#667eea', 0.5)}`,
  },
}));

const PlayOverlay = styled(Box)({
  position: 'absolute',
  top: 0,
  left: 0,
  right: 0,
  bottom: 0,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  background: 'rgba(0, 0, 0, 0.65)',
  backdropFilter: 'blur(4px)',
  opacity: 0,
  transition: `opacity ${transitions.normal}`,
  zIndex: 2,
});

const PlayButton = styled(IconButton)({
  background: gradients.aurora,
  width: '72px',
  height: '72px',
  color: colors.text.primary,
  boxShadow: shadows.glowPurple,
  transition: `all ${transitions.normal}`,

  '&:hover': {
    background: gradients.aurora,
    transform: 'scale(1.15)',
    boxShadow: shadows.xl,
  },

  '&:active': {
    transform: 'scale(1.05)',
  },

  '& .MuiSvgIcon-root': {
    fontSize: '36px',
  },
});

const MoreButton = styled(IconButton)({
  position: 'absolute',
  top: `${spacing.sm}px`,
  right: `${spacing.sm}px`,
  background: 'rgba(0, 0, 0, 0.6)',
  backdropFilter: 'blur(8px)',
  color: colors.text.primary,
  opacity: 0,
  transition: `all ${transitions.normal}`,
  zIndex: 3,

  '&:hover': {
    background: 'rgba(0, 0, 0, 0.8)',
    transform: 'scale(1.1)',
    boxShadow: shadows.md,
  },

  '&:active': {
    transform: 'scale(0.95)',
  },
});

const PlaceholderBox = styled(Box)({
  width: '100%',
  paddingTop: '100%', // 1:1 aspect ratio
  position: 'relative',
  background: gradients.aurora,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
});

const PlaceholderIcon = styled(Box)({
  position: 'absolute',
  top: '50%',
  left: '50%',
  transform: 'translate(-50%, -50%)',
  fontSize: '64px',
  color: 'rgba(255, 255, 255, 0.3)',
  fontWeight: 300,
});

export const AlbumCard: React.FC<AlbumCardProps> = ({
  id,
  title,
  artist,
  albumId,
  albumArt,
  trackCount,
  onPlay,
  onContextMenu,
}) => {
  const { contextMenuState, handleContextMenu: handleContextMenuBase, handleCloseContextMenu } = useContextMenu();
  const { success, info } = useToast();

  const handlePlay = (e: React.MouseEvent) => {
    e.stopPropagation();
    onPlay(id);
  };

  const handleContextMenuOpen = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    handleContextMenuBase(e);
    onContextMenu?.(id, e);
  };

  const handleMoreClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    // Simulate context menu at button position
    const rect = e.currentTarget.getBoundingClientRect();
    const syntheticEvent = {
      preventDefault: () => {},
      stopPropagation: () => {},
      clientX: rect.right,
      clientY: rect.bottom,
    } as React.MouseEvent;
    handleContextMenuBase(syntheticEvent);
  };

  const handleCardClick = () => {
    onPlay(id);
  };

  // Context menu actions
  const contextActions = getAlbumContextActions(id, {
    onPlay: () => {
      onPlay(id);
      success(`Playing "${title}"`);
    },
    onAddToQueue: () => {
      success(`Added "${title}" to queue`);
      // TODO: Implement actual queue functionality
    },
    onShowArtist: () => {
      info(`Showing artist: ${artist}`);
      // TODO: Navigate to artist view
    },
    onEdit: () => {
      info(`Edit album: ${title}`);
      // TODO: Open album edit dialog
    },
  });

  return (
    <>
      <StyledCard
        onClick={handleCardClick}
        onContextMenu={handleContextMenuOpen}
        tabIndex={0}
        component="div"
      >
        <Box position="relative" sx={{ overflow: 'hidden', borderRadius: `${borderRadius.sm}px` }}>
          {/* Use AlbumArt component for real artwork extraction */}
          <Box sx={{ width: '100%', aspectRatio: '1/1' }}>
            <AlbumArt albumId={albumId} size="100%" borderRadius={0} />
          </Box>

          <PlayOverlay className="play-overlay">
            <PlayButton onClick={handlePlay} aria-label="Play album" disableRipple={false}>
              <PlayArrow />
            </PlayButton>
          </PlayOverlay>

          <MoreButton
            className="more-button"
            onClick={handleMoreClick}
            aria-label="More options"
            size="small"
          >
            <MoreVert fontSize="small" />
          </MoreButton>
        </Box>

      <CardContent sx={{ p: `${spacing.md}px`, pb: `${spacing.md}px !important` }}>
        <Typography
          className="album-title"
          variant="subtitle1"
          sx={{
            color: colors.text.primary,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            mb: `${spacing.xs}px`,
            transition: `color ${transitions.fast}`,
            fontWeight: 600,
          }}
        >
          {title}
        </Typography>
        <Typography
          variant="body2"
          sx={{
            color: colors.text.secondary,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            mb: trackCount ? `${spacing.xs}px` : 0,
          }}
        >
          {artist}
        </Typography>
        {trackCount && (
          <Typography
            variant="caption"
            sx={{
              color: colors.text.disabled,
              display: 'block',
            }}
          >
            {trackCount} {trackCount === 1 ? 'track' : 'tracks'}
          </Typography>
        )}
      </CardContent>
      </StyledCard>

      {/* Context menu */}
      <ContextMenu
        anchorPosition={contextMenuState.mousePosition}
        open={contextMenuState.isOpen}
        onClose={handleCloseContextMenu}
        actions={contextActions}
      />
    </>
  );
};

export default AlbumCard;
