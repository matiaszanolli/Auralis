/**
 * AppEnhancementPane Styled Components
 * Updated for Auralis Design Language v1.2.0
 */

import { Box, styled } from '@mui/material';
import { tokens } from '@/design-system';

/**
 * PaneContainer - Enhancement panel container (Design Language v1.2.0 §4.1)
 * Calm by default, glass surface with subtle borders
 */
export const PaneContainer = styled(Box, {
  shouldForwardProp: (prop) => prop !== 'isCollapsed',
})<{ isCollapsed: boolean }>(({ isCollapsed }) => ({
  display: 'flex',
  flexDirection: 'column',

  // Glass surface - upgraded to medium for more presence (§4.1)
  background: tokens.glass.medium.background,
  backdropFilter: tokens.glass.medium.backdropFilter,   // 32px blur for stronger glass effect
  border: tokens.glass.medium.border,                   // 18% white opacity for better light-catching
  boxShadow: tokens.glass.medium.boxShadow,             // Deeper shadow + inner glow

  transition: `width ${tokens.transitions.slow}`,  // Slow, heavy motion (§5)
  width: isCollapsed ? 60 : 320,
  minWidth: isCollapsed ? 60 : 320,
  height: '100%',
  overflow: 'hidden',
}));

/**
 * PaneHeader - Header section for panel
 * No borders - separation via spacing only (§4.1)
 */
export const PaneHeader = styled(Box)({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  padding: `${tokens.spacing.md} ${tokens.spacing.sm}`,
  borderBottom: 'none',  // No borders - depth via spacing (§4.1)
  gap: tokens.spacing.md,
  marginBottom: tokens.spacing.sm,  // Spacing for visual separation
});

/**
 * PaneTitle - Section label (Design Language v1.2.0 §3)
 * Typography disappears - lower opacity, minimal weight
 */
export const PaneTitle = styled(Box)({
  fontSize: tokens.typography.fontSize.xs,
  fontWeight: tokens.typography.fontWeight.medium,
  color: tokens.colors.text.disabled,
  textTransform: 'uppercase',
  letterSpacing: '1px',
  flex: 1,
  opacity: 0.6,  // Fade labels - they're infrastructure, not content
});

/**
 * ContentArea - Scrollable content area
 * Minimal scrollbar styling, transparent track
 */
export const ContentArea = styled(Box)({
  flex: 1,
  overflow: 'auto',
  padding: `${tokens.spacing.lg} ${tokens.spacing.md}`,
  '&::-webkit-scrollbar': {
    width: '6px',
  },
  '&::-webkit-scrollbar-track': {
    background: 'transparent',
  },
  '&::-webkit-scrollbar-thumb': {
    background: tokens.colors.accent.primary,
    opacity: 0.3,
    borderRadius: tokens.borderRadius.sm,
    '&:hover': {
      opacity: 0.5,
    },
  },
});

/**
 * FooterArea - Footer section for panel
 * No borders - depth via spacing only (§4.1)
 */
export const FooterArea = styled(Box)({
  padding: `${tokens.spacing.md} ${tokens.spacing.sm}`,
  borderTop: 'none',  // No borders - separation via spacing (§4.1)
  marginTop: tokens.spacing.sm,  // Spacing for visual separation
  display: 'flex',
  gap: tokens.spacing.sm,
});
