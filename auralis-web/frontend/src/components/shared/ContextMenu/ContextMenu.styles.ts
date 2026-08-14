import { Menu, MenuItem, styled } from '@mui/material';
import { tokens } from '@/design-system';
import { themeVars } from '@/theme/semanticTheme';

/**
 * StyledMenu - Context menu background with backdrop blur
 */
export const StyledMenu = styled(Menu)({
  '& .MuiPaper-root': {
    background: themeVars.surfaceSecondary,
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
    color: destructive ? tokens.colors.semantic.error : themeVars.textPrimary,
    transition: tokens.transitions.base_inOut,

    '&:hover': {
      background: destructive ? themeVars.surfaceRaised : themeVars.surfaceOverlay,
    },

    '&.Mui-disabled': {
      // #4635 lists this among the sites to swap to text.metadata, but this one
      // is genuinely an inactive control — WCAG 2.1 SC 1.4.3 exempts "text that
      // is part of an inactive user interface component" from the 4.5:1 minimum,
      // which is the same reasoning the issue uses to leave VolumeControl and
      // PlaybackControls alone. Swapping here would also erase the visual
      // distinction between an enabled and a disabled menu item, which is the
      // information this style exists to convey. Token kept deliberately.
      color: themeVars.textDisabled,
      // The compounded `opacity: 0.5` IS removed: 40% x 50% is ~20% effective
      // alpha (~1.9:1), which stops reading as "disabled" and starts reading as
      // "not there". The token is already the faded treatment; multiplying it
      // was double-fading, the same anti-pattern #4451 called out.
    },

    '& .MuiListItemIcon-root': {
      color: destructive ? tokens.colors.semantic.error : themeVars.textSecondary,
      minWidth: 36,
    },
  })
);
