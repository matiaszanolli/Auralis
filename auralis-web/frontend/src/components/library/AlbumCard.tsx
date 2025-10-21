import React, { useState } from 'react';
import { Card, CardMedia, CardContent, Typography, Box, IconButton, styled } from '@mui/material';
import { PlayArrow, MoreVert } from '@mui/icons-material';
import { colors, gradients } from '../../theme/auralisTheme';
import AlbumArt from '../album/AlbumArt';
// import { useContextMenu, ContextMenu, getAlbumContextActions } from '../shared/ContextMenu';
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
  borderRadius: '8px',
  overflow: 'hidden',
  cursor: 'pointer',
  transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
  border: `1px solid transparent`,

  '&:hover': {
    transform: 'translateY(-4px) scale(1.02)',
    boxShadow: `0 12px 32px rgba(102, 126, 234, 0.25), 0 0 0 1px rgba(102, 126, 234, 0.1)`,
    border: `1px solid rgba(102, 126, 234, 0.3)`,
  },

  '&:hover .play-overlay': {
    opacity: 1,
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
  transition: 'opacity 0.3s ease',
  zIndex: 2,
});

const PlayButton = styled(IconButton)({
  background: gradients.aurora,
  width: '72px',
  height: '72px',
  color: '#ffffff',
  boxShadow: '0 8px 24px rgba(102, 126, 234, 0.4)',
  transition: 'all 0.3s ease',

  '&:hover': {
    background: gradients.aurora,
    transform: 'scale(1.15)',
    boxShadow: '0 12px 32px rgba(102, 126, 234, 0.6)',
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
  top: '8px',
  right: '8px',
  background: 'rgba(0, 0, 0, 0.6)',
  backdropFilter: 'blur(8px)',
  color: '#ffffff',
  opacity: 0,
  transition: 'opacity 0.3s ease',
  zIndex: 3,

  '&:hover': {
    background: 'rgba(0, 0, 0, 0.8)',
  },

  '.MuiCard-root:hover &': {
    opacity: 1,
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
  // Context menu state - temporarily disabled for build
  // const { contextMenuState, handleContextMenu: handleContextMenuBase, handleCloseContextMenu } = useContextMenu();
  const { success, info } = useToast();

  const handlePlay = (e: React.MouseEvent) => {
    e.stopPropagation();
    onPlay(id);
  };

  // const handleContextMenu = (e: React.MouseEvent) => {
  //   e.preventDefault();
  //   e.stopPropagation();
  //   handleContextMenuBase(e);
  //   onContextMenu?.(id, e);
  // };

  const handleMoreClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    // Context menu temporarily disabled
    info('Context menu coming soon!');
  };

  const handleCardClick = () => {
    onPlay(id);
  };

  // Context menu actions - temporarily disabled
  // const contextActions = getAlbumContextActions(id, {
  //   onPlay: () => {
  //     onPlay(id);
  //     info(`Playing ${title}`);
  //   },
  //   onAddToQueue: () => {
  //     success(`Added "${title}" to queue`);
  //   },
  //   onAddToPlaylist: () => {
  //     info('Select playlist'); // TODO: Show playlist selector modal
  //   },
  //   onShowInfo: () => {
  //     info(`Album: ${title} by ${artist}`); // TODO: Show album info modal
  //   },
  // });

  return (
    <StyledCard onClick={handleCardClick}>
      <Box position="relative">
        {/* Use AlbumArt component for real artwork extraction */}
        <Box sx={{ width: '100%', aspectRatio: '1/1' }}>
          <AlbumArt albumId={albumId} size="100%" borderRadius={0} />
        </Box>

        <PlayOverlay className="play-overlay">
          <PlayButton onClick={handlePlay} aria-label="Play">
            <PlayArrow />
          </PlayButton>
        </PlayOverlay>

        <MoreButton onClick={handleMoreClick} aria-label="More options" size="small">
          <MoreVert fontSize="small" />
        </MoreButton>
      </Box>

      <CardContent sx={{ p: 2, pb: '16px !important' }}>
        <Typography
          variant="body1"
          sx={{
            color: colors.text.primary,
            fontWeight: 600,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            mb: 0.5,
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
            mb: trackCount ? 0.5 : 0,
          }}
        >
          {artist}
        </Typography>
        {trackCount && (
          <Typography variant="caption" sx={{ color: colors.text.disabled }}>
            {trackCount} {trackCount === 1 ? 'track' : 'tracks'}
          </Typography>
        )}
      </CardContent>

      {/* Context menu temporarily disabled */}
      {/* <ContextMenu
        anchorPosition={contextMenuState.mousePosition}
        open={contextMenuState.isOpen}
        onClose={handleCloseContextMenu}
        actions={contextActions}
      /> */}
    </StyledCard>
  );
};

export default AlbumCard;
