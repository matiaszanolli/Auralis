import { Box, ListItemButton, Typography, styled } from '@mui/material';
import { tokens, withOpacity } from '@/design-system/tokens';

/**
 * Styled components for Sidebar
 */

export const SidebarContainer = styled(Box)({
  width: tokens.components.sidebar.width,
  height: '100%',
  background: tokens.colors.bg.secondary,
  borderRight: `1px solid ${tokens.colors.border.light}`,
  display: 'flex',
  flexDirection: 'column',
  transition: `width ${tokens.transitions.slow}`,
});

export const SectionLabel = styled(Typography)({
  fontSize: tokens.typography.fontSize.xs,
  fontWeight: tokens.typography.fontWeight.semibold,
  color: tokens.colors.text.disabled,
  textTransform: 'uppercase',
  letterSpacing: '1px',
  padding: `${tokens.spacing.md} ${tokens.spacing.lg} ${tokens.spacing.sm}`,
});

export const StyledListItemButton = styled(ListItemButton)<{ isactive?: string }>(({ isactive }) => ({
  borderRadius: tokens.borderRadius.md,
  height: `calc(${tokens.spacing.lg} + ${tokens.spacing.md})`, // 40px (24 + 16)
  marginBottom: tokens.spacing.xs,
  position: 'relative',
  transition: tokens.transitions.all,

  ...(isactive === 'true' && {
    background: withOpacity(tokens.colors.accent.primary, 0.15),
    '&::before': {
      content: '""',
      position: 'absolute',
      left: 0,
      top: 0,
      bottom: 0,
      width: '3px',
      background: tokens.gradients.aurora,
      borderRadius: '0 2px 2px 0',
    },
  }),

  '&:hover': {
    background: isactive === 'true'
      ? withOpacity(tokens.colors.accent.primary, 0.2)
      : tokens.colors.bg.elevated,
    transform: 'translateX(2px)',
  },
}));

export const CollapsedSidebarContainer = styled(Box)({
  width: tokens.spacing.xxxl, // 64px
  height: '100%',
  background: tokens.colors.bg.secondary,
  borderRight: `1px solid ${tokens.colors.border.light}`,
  display: 'flex',
  flexDirection: 'column',
  transition: `width ${tokens.transitions.slow}`,
});
