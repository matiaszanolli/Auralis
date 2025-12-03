import { Menu, MenuItem, styled } from '@mui/material';
import { tokens } from '@/design-system';

/**
 * StyledMenu - Context menu background with backdrop blur
 */
export const StyledMenu = styled(Menu)({
  '& .MuiPaper-root': {
    background: tokens.colors.bg.level2,
    border: `1px solid ${tokens.colors.border.light}`,
    boxShadow: tokens.shadows.lg,
    borderRadius: tokens.borderRadius.md,
    minWidth: '220px',
    padding: tokens.spacing.sm,
    backdropFilter: 'blur(12px)',
  },
});

/**
 * StyledMenuItem - Menu item with optional destructive styling
 *
 * Supports destructive variant (red) for delete/destructive actions
 */
export const StyledMenuItem = styled(MenuItem)<{ destructive?: boolean }>(
  ({ destructive }) => ({
    borderRadius: tokens.borderRadius.sm,
    padding: `${tokens.spacing.md} ${tokens.spacing.md}`,
    margin: `${tokens.spacing.sm} 0`,
    fontSize: tokens.typography.fontSize.base,
    color: destructive ? tokens.colors.semantic.error : tokens.colors.text.primary,
    transition: tokens.transitions.base_inOut,

    '&:hover': {
      background: destructive ? tokens.colors.bg.level3 : tokens.colors.bg.level4,
    },

    '&.Mui-disabled': {
      color: tokens.colors.text.disabled,
      opacity: 0.5,
    },

    '& .MuiListItemIcon-root': {
      color: destructive ? tokens.colors.semantic.error : tokens.colors.text.secondary,
      minWidth: 36,
    },
  })
);
