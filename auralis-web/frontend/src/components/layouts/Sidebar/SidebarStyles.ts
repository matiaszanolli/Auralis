import { Box, ListItemButton, Typography, styled } from '@mui/material';
import { tokens, withOpacity } from '@/design-system';

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

  // Lower contrast glass (calm, muscle memory UI)
  background: tokens.components.sidebar.background,
  backdropFilter: tokens.components.sidebar.backdropFilter,
  borderRight: tokens.components.sidebar.borderRight,  // 'none' from tokens
  boxShadow: tokens.components.sidebar.shadow,

  display: 'flex',
  flexDirection: 'column',
  transition: `width ${tokens.transitions.slow}, backdrop-filter ${tokens.transitions.base}`,

  // No edge glow - sidebar should fade from conscious awareness (§4.3)
});

export const SectionLabel = styled(Typography)({
  fontSize: tokens.typography.fontSize.xs,
  fontWeight: tokens.typography.fontWeight.medium, // Reduced from semibold
  color: tokens.colors.text.disabled,
  textTransform: 'uppercase',
  letterSpacing: '1px',
  padding: `${tokens.spacing.md} ${tokens.spacing.lg} ${tokens.spacing.sm}`,
  opacity: 0.4, // Fade even more (~60%) to make labels fade into background (§4.3)
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

  ...(isactive === 'true' && {
    // Enhanced active state - more visible with stronger glass
    background: tokens.glass.subtle.background,  // Use glass tokens for consistency
    backdropFilter: tokens.glass.subtle.backdropFilter, // 20px blur for glossy effect
    border: tokens.glass.subtle.border,         // Subtle glass border (10% white opacity)
    boxShadow: tokens.glass.subtle.boxShadow,   // Deeper shadow + inner glow

    '&::before': {
      content: '""',
      position: 'absolute',
      left: 0,
      top: 0,
      bottom: 0,
      width: '3px',                            // More visible accent bar
      background: tokens.colors.accent.primary,
      borderRadius: '0 2px 2px 0',             // Softer curve
      boxShadow: `0 0 8px ${tokens.colors.accent.primary}66`, // Subtle glow
    },
  }),

  '&:hover': {
    background: isactive === 'true'
      ? tokens.glass.medium.background         // Enhanced glass on hover
      : tokens.glass.subtle.background,        // Glass effect on hover
    backdropFilter: isactive === 'true'
      ? tokens.glass.medium.backdropFilter     // 32px blur (intensified from 28px)
      : tokens.glass.subtle.backdropFilter,    // 24px blur (intensified from 20px)
    transform: 'scale(1.01)',                  // Subtle scale hover (Design Language §5 - muscle memory UI)
    boxShadow: tokens.glass.subtle.boxShadow,  // Add depth on hover
    border: tokens.glass.subtle.border,        // Glass border on hover (15% white opacity)
  },
}));

export const CollapsedSidebarContainer = styled(Box)({
  width: tokens.spacing.xxxl, // 64px
  alignSelf: 'stretch', // Use flex stretch instead of height: 100%
  flexShrink: 0,
  // Semi-transparent to let starfield show through
  background: 'rgba(16, 23, 41, 0.45)',  // secondary color at 45% opacity for starfield visibility
  backdropFilter: 'blur(6px) saturate(0.95)',  // Softer blur to preserve starfield
  // Removed hard border, using shadow for depth instead
  boxShadow: '2px 0 16px rgba(0, 0, 0, 0.12)', // Subtle right shadow for separation
  display: 'flex',
  flexDirection: 'column',
  transition: `width ${tokens.transitions.slow}`,
});
