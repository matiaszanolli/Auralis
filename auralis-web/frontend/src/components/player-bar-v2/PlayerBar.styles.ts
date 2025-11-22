/**
 * Player Bar Styles - Reusable player bar component styling
 *
 * Consolidates styled components from BottomPlayerBarUnified
 * to improve modularity and maintainability.
 * Shadow effects are imported from Shadow.styles.ts.
 * Border radius values are imported from BorderRadius.styles.ts.
 */

import { Box, IconButton, styled } from '@mui/material';
import { gradients } from '../../theme/auralisTheme';
import { compoundShadows } from '../library/Shadow.styles';
import { radiusMedium } from '../library/BorderRadius.styles';

/**
 * PlayerContainer - Main fixed player bar container
 * Positioned at bottom of screen with gradient background and backdrop blur
 */
export const PlayerContainer = styled(Box)({
  position: 'fixed',
  bottom: 0,
  left: 0,
  right: 0,
  width: '100vw',
  height: '80px',
  margin: 0,
  padding: 0,
  background: 'linear-gradient(180deg, rgba(10, 14, 39, 0.98) 0%, rgba(10, 14, 39, 0.99) 100%)',
  backdropFilter: 'blur(20px)',
  WebkitBackdropFilter: 'blur(20px)', // Safari support
  borderTop: `1px solid rgba(102, 126, 234, 0.15)`,
  display: 'flex',
  flexDirection: 'column',
  zIndex: 1300, // Higher than MUI modals (1200)
  boxShadow: compoundShadows.playerContainer,
});

/**
 * PlayButton - Primary play/pause button with gradient
 */
export const PlayButton = styled(IconButton)({
  background: gradients.aurora,
  color: '#ffffff',
  width: '56px',
  height: '56px',
  minWidth: '56px',
  flexShrink: 0,
  boxShadow: compoundShadows.playerButton,
  transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',

  '&:hover': {
    background: gradients.aurora,
    transform: 'scale(1.05)',
    boxShadow: compoundShadows.playerButtonHover,
  },

  '&:active': {
    transform: 'scale(0.98)',
  },

  '&:disabled': {
    background: 'rgba(102, 126, 234, 0.2)',
    color: 'rgba(255, 255, 255, 0.3)',
  },
});

/**
 * AlbumArtContainer - Album artwork display area
 */
export const AlbumArtContainer = styled(Box)({
  width: '64px',
  height: '64px',
  borderRadius: radiusMedium,
  marginRight: '12px',
  flexShrink: 0,
  overflow: 'hidden',
  background: 'rgba(255,255,255,0.1)',
  border: '1px solid rgba(255,255,255,0.1)',
});

/**
 * ControlButton - Secondary control buttons (skip, previous, volume)
 */
export const ControlButton = styled(IconButton)({
  color: 'rgba(255,255,255,0.7)',
  width: '40px',
  height: '40px',
  minWidth: '40px',
  flexShrink: 0,

  '&:hover': {
    color: '#ffffff',
    background: 'rgba(102, 126, 234, 0.1)',
  },

  '&:disabled': {
    color: 'rgba(255,255,255,0.3)',
  },
});

export default PlayerContainer;
