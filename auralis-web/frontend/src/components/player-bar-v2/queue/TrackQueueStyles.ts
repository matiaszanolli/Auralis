/**
 * TrackQueue Styled Components
 */

import { Box, Typography, List, ListItem, styled } from '@mui/material';
import { PlayArrow } from '@mui/icons-material';
import { gradients } from '../../library/Color.styles';
import { auroraOpacity } from '../../library/Color.styles';
import { tokens } from '@/design-system/tokens';

export const QueueContainer = styled(Box)(({ theme }) => ({
  width: '100%',
  background: tokens.colors.bg.secondary,
  borderRadius: '8px',
  padding: '16px',
  marginTop: '24px',
  border: `1px solid ${auroraOpacity.veryLight}`,
}));

export const QueueHeader = styled(Typography)(({ theme }) => ({
  fontSize: '14px',
  fontWeight: 600,
  color: tokens.colors.text.secondary,
  textTransform: 'uppercase',
  letterSpacing: '0.5px',
  marginBottom: '12px',
  paddingLeft: '8px',
}));

export const QueueList = styled(List)({
  padding: 0,
  '& .MuiListItem-root': {
    padding: 0,
  },
});

export const TrackItem = styled(ListItem)<{ isactive?: string }>(({ isactive }) => ({
  height: '48px',
  padding: '0 12px',
  borderRadius: '6px',
  cursor: 'pointer',
  transition: 'all 0.2s ease',
  marginBottom: '4px',
  background: isactive === 'true' ? auroraOpacity.lighter : 'transparent',
  border: isactive === 'true' ? `1px solid ${auroraOpacity.strong}` : '1px solid transparent',
  position: 'relative',

  '&:hover': {
    background: isactive === 'true'
      ? auroraOpacity.standard
      : tokens.colors.bg.elevated,
    transform: 'translateX(4px)',

    '& .play-indicator': {
      opacity: 1,
    },
  },

  '&:last-child': {
    marginBottom: 0,
  },
}));

export const TrackNumber = styled(Typography)<{ isactive?: string }>(({ isactive }) => ({
  fontSize: '14px',
  fontWeight: 500,
  color: isactive === 'true' ? tokens.colors.accent.purple : tokens.colors.text.secondary,
  minWidth: '32px',
  textAlign: 'center',
  transition: 'color 0.2s ease',
}));

export const TrackTitle = styled(Typography)<{ isactive?: string }>(({ isactive }) => ({
  fontSize: '14px',
  fontWeight: isactive === 'true' ? 600 : 400,
  color: tokens.colors.text.primary,
  flex: 1,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
  paddingRight: '12px',
  transition: 'all 0.2s ease',
}));

export const TrackDuration = styled(Typography)<{ isactive?: string }>(({ isactive }) => ({
  fontSize: '14px',
  fontWeight: 400,
  color: isactive === 'true' ? tokens.colors.text.secondary : tokens.colors.text.disabled,
  minWidth: '50px',
  textAlign: 'right',
  transition: 'color 0.2s ease',
}));

export const PlayIndicator = styled(PlayArrow)({
  position: 'absolute',
  left: '8px',
  fontSize: '16px',
  color: tokens.colors.accent.purple,
  opacity: 0,
  transition: 'opacity 0.2s ease',
});

export const ActiveIndicator = styled(Box)({
  position: 'absolute',
  left: 0,
  top: 0,
  bottom: 0,
  width: '3px',
  background: gradients.aurora,
  borderRadius: '0 2px 2px 0',
});
