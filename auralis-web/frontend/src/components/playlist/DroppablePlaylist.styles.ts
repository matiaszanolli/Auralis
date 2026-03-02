import { styled } from '@mui/material/styles';
import { Box, ListItemButton, Typography } from '@mui/material';
import QueueMusicIcon from '@mui/icons-material/QueueMusic';
import { tokens } from '@/design-system';

export const StyledListItemButton = styled(ListItemButton, {
  shouldForwardProp: (prop) => prop !== 'isDraggingOver' && prop !== 'selected',
})<{ isDraggingOver?: boolean; selected?: boolean }>(({ theme, isDraggingOver, selected }) => ({
  borderRadius: theme.spacing(1),
  marginBottom: theme.spacing(0.5),
  padding: theme.spacing(1, 2),
  transition: 'all 0.2s ease',
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
        : 'rgba(255, 255, 255, 0.05)',
  },
}));

export const PlaylistIcon = styled(QueueMusicIcon)(({ theme }) => ({
  marginRight: theme.spacing(2),
  color: theme.palette.text.secondary,
}));

export const TrackCount = styled(Typography)<{ component?: React.ElementType }>(({ theme }) => ({
  fontSize: '0.75rem',
  color: theme.palette.text.secondary,
  marginLeft: theme.spacing(1),
}));

export const DropIndicator = styled(Box)(({ theme }) => ({
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
  borderRadius: theme.spacing(1),
  pointerEvents: 'none',
  zIndex: 1,
}));

export const DropIndicatorText = styled(Typography)(({ theme }) => ({
  color: theme.palette.primary.main,
  fontWeight: 600,
  fontSize: '0.875rem',
}));

export const DroppableContainer = styled(Box)({
  position: 'relative',
});

export const PlaceholderContainer = styled(Box)({
  display: 'none',
});
