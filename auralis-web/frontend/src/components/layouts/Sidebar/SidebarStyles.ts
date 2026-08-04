import { Box, ListItemButton, styled } from '@mui/material';
import { tokens } from '@/design-system';
import { themeVars } from '@/theme/semanticTheme';

/**
 * Styled components for Sidebar
 */

/**
 * Sidebar Container (Design Language §4.3)
 * Muscle memory UI - lower contrast, no visual drama.
 * Separates via spacing and subtle depth, not borders.
 */
export const SidebarContainer = styled(Box)({
  width: tokens.components.sidebar.width,
  // Use alignSelf: stretch instead of height: 100% for proper flex behavior
  // This ensures the sidebar fills the full height in nested flex layouts
  alignSelf: 'stretch',
  flexShrink: 0,

  background: themeVars.surfacePrimary,
  borderRight: `1px solid ${themeVars.borderSubtle}`,

  display: 'flex',
  flexDirection: 'column',
  transition: `width ${tokens.transitions.slow}`,

  // No edge glow - sidebar should fade from conscious awareness (§4.3)
});

export const SectionLabel = styled('h2')({
  margin: 0,
  fontSize: tokens.typography.fontSize.xs,
  fontWeight: tokens.typography.fontWeight.medium, // Reduced from semibold
  // text.metadata (60% white) is validated for WCAG AA 4.5:1 on small text;
  // text.disabled (40%) is only calibrated for the 3:1 large-text minimum, and
  // the previous extra `opacity: 0.4` compounded it to ~16% effective alpha —
  // near-invisible and well under AA against the dark glass sidebar (#4451).
  color: themeVars.textMuted,
  textTransform: 'uppercase',
  letterSpacing: '1px',
  padding: `${tokens.spacing.md} ${tokens.spacing.lg} ${tokens.spacing.sm}`,
});

/**
 * Sidebar List Item Button (Design Language §4.3)
 * Active state is subtle, not loud. Lower contrast for muscle memory UI.
 * No borders - depth via subtle background and minimal glow.
 */
export const StyledListItemButton = styled(ListItemButton)<{ isactive?: string }>(({ isactive }) => ({
  borderRadius: tokens.borderRadius.md,      // 12px - softer, more organic
  height: `calc(${tokens.spacing.lg} + ${tokens.spacing.md})`, // 40px (20 + 12)
  marginBottom: tokens.spacing.cluster,      // 8px - tight clustering within sections
  position: 'relative',
  transition: `${tokens.transitions.all}, backdrop-filter ${tokens.transitions.base}`,
  border: '1px solid transparent',

  ...(isactive === 'true' && {
    background: themeVars.accentSoft,
    borderColor: themeVars.borderStrong,

    '&::before': {
      content: '""',
      position: 'absolute',
      left: 0,
      top: 0,
      bottom: 0,
      width: '3px',                            // More visible accent bar
      background: themeVars.accent,
      borderRadius: '0 2px 2px 0',             // Softer curve
    },
  }),

  '&:hover': {
    background: themeVars.accentSoft,
    borderColor: isactive === 'true' ? themeVars.borderStrong : 'transparent',
  },
}));

export const CollapsedSidebarContainer = styled(Box)({
  width: tokens.spacing.xxxl, // 64px
  alignSelf: 'stretch', // Use flex stretch instead of height: 100%
  flexShrink: 0,
  background: themeVars.surfacePrimary,
  borderRight: `1px solid ${themeVars.borderSubtle}`,
  display: 'flex',
  flexDirection: 'column',
  transition: `width ${tokens.transitions.slow}`,
});
