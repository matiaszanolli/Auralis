/**
 * EnhancementPane Styled Components
 * Updated for Auralis Design Language v1.2.0
 * Glass surfaces with organic spacing and soft borders
 */

import { styled } from '@mui/material/styles';
import { Box, Stack } from '@mui/material';
import { tokens } from '@/design-system';

/**
 * CollapsedPaneContainer - Compact collapsed state (Design Language §4.1)
 * Glass surface with subtle depth
 */
export const CollapsedPaneContainer = styled(Box)({
  width: tokens.spacing.xxxl,                             // 56px
  height: '100%',

  // Glass effect for collapsed pane
  background: tokens.glass.subtle.background,             // Semi-transparent glass
  backdropFilter: tokens.glass.subtle.backdropFilter,     // 20px blur for glossy effect
  borderLeft: tokens.glass.subtle.border,                 // Subtle glass border (10% white opacity)
  boxShadow: tokens.glass.subtle.boxShadow,               // Depth + inner glow

  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  paddingTop: tokens.spacing.md,
  paddingBottom: tokens.spacing.md,
  transition: `width ${tokens.transitions.slow}, backdrop-filter ${tokens.transitions.base}`,
});

/**
 * ExpandedPaneContainer - Full width expanded state (Design Language §4.1)
 * Medium glass effect for elevated presence
 */
export const ExpandedPaneContainer = styled(Box)({
  width: tokens.components.rightPanel.width,              // 320px
  height: '100%',

  // Glass effect for expanded pane (medium strength)
  background: tokens.glass.medium.background,             // Semi-transparent background
  backdropFilter: tokens.glass.medium.backdropFilter,     // 28px blur + saturation
  border: 'none',
  borderLeft: tokens.glass.medium.border,                 // Subtle glass border separator
  boxShadow: tokens.glass.medium.boxShadow,               // Deeper shadow + inner glow

  display: 'flex',
  flexDirection: 'column',
  transition: `width ${tokens.transitions.slow}, backdrop-filter ${tokens.transitions.base}`,
  overflow: 'hidden',
});

/**
 * PaneHeader - Header section (Design Language §4.1)
 * Subtle glass background for depth layering, no hard borders
 */
export const PaneHeader = styled(Box)({
  padding: tokens.spacing.lg,                             // 20px - organic breathing room
  paddingBottom: tokens.spacing.md,                       // 12px - asymmetric for cleaner look

  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',

  // Subtle glass background for depth separation (no hard borders)
  background: tokens.glass.subtle.background,             // Very subtle glass tint
  backdropFilter: 'blur(12px)',                           // Lighter blur for header
  borderBottom: 'none',                                   // No borders - depth via spacing
});

/**
 * PaneContent - Scrollable content area (Design Language §4.1)
 * Organic spacing with custom scrollbar
 */
export const PaneContent = styled(Box)({
  flex: 1,
  padding: tokens.spacing.section,                        // 32px - organic section spacing
  paddingTop: tokens.spacing.group,                       // 16px - less top padding (header has padding)
  overflowY: 'auto',

  // Transparent background - inherits glass from container
  background: 'transparent',

  // Custom scrollbar for organic feel
  '&::-webkit-scrollbar': {
    width: '6px',
  },
  '&::-webkit-scrollbar-track': {
    background: 'transparent',
  },
  '&::-webkit-scrollbar-thumb': {
    background: tokens.colors.accent.primary,
    opacity: 0.3,
    borderRadius: tokens.borderRadius.sm,                 // 8px - soft curves
    '&:hover': {
      opacity: 0.5,
    },
  },
});

export const CollapsedIconContainer = styled(Box)({
  marginTop: tokens.spacing.md,
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  gap: tokens.spacing.md,
});

export const DisabledStateContainer = styled(Box)({
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  textAlign: 'center',
  marginTop: tokens.spacing.xl,
});

export const ParametersStack = styled(Stack)({
  spacing: tokens.spacing.lg,
});
