import { styled } from '@mui/material/styles';
import { Box, ListItemButton, Typography } from '@mui/material';
import QueueMusicIcon from '@mui/icons-material/QueueMusic';
import { tokens } from '@/design-system';

export const StyledListItemButton = styled(ListItemButton, {
  shouldForwardProp: (prop) => prop !== 'isDraggingOver' && prop !== 'selected',
})<{ isDraggingOver?: boolean; selected?: boolean }>(({ isDraggingOver, selected }) => ({
  borderRadius: tokens.spacing.xs,
  marginBottom: '2px',
  padding: `${tokens.spacing.xs} ${tokens.spacing.sm}`,
  transition: tokens.transitions.hover_out,
  backgroundColor: isDraggingOver
    ? tokens.colors.opacityScale.accent.standard
    : selected
      ? tokens.colors.opacityScale.accent.veryLight
      : 'transparent',
  border: isDraggingOver ? `2px dashed ${tokens.colors.opacityScale.accent.veryStrong}` : '2px solid transparent',

  '&:hover': {
    backgroundColor: isDraggingOver
      ? tokens.colors.opacityScale.accent.light
      : selected
        ? tokens.colors.opacityScale.accent.lighter
        : tokens.colors.opacityScale.white.veryLight,
  },
}));

export const PlaylistIcon = styled(QueueMusicIcon)({
  marginRight: tokens.spacing.sm,
  color: tokens.colors.text.secondary,
});

export const TrackCount = styled(Typography)<{ component?: React.ElementType }>({
  fontSize: tokens.typography.fontSize.sm,
  color: tokens.colors.text.secondary,
  marginLeft: tokens.spacing.xs,
});

export const DropIndicator = styled(Box)({
  position: 'absolute',
  top: 0,
  left: 0,
  right: 0,
  bottom: 0,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  backgroundColor: tokens.colors.opacityScale.accent.veryLight,
  border: `2px dashed ${tokens.colors.opacityScale.accent.veryStrong}`,
  borderRadius: tokens.spacing.xs,
  pointerEvents: 'none',
  zIndex: tokens.zIndex.content,
});

export const DropIndicatorText = styled(Typography)({
  color: tokens.colors.accent.primary,
  fontWeight: tokens.typography.fontWeight.semibold,
  fontSize: tokens.typography.fontSize.base,
});

export const DroppableContainer = styled(Box)({
  position: 'relative',
});

export const PlaceholderContainer = styled(Box)({
  display: 'none',
});
