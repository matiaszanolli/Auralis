/**
 * Player component styles using design tokens (Design Language v1.2.0)
 *
 * Layout:
 * - Top: Progress bar with buffering
 * - Bottom: Track display + playback controls + volume
 *
 * Glass Effects: Applied to main container for elevated, glossy aesthetic
 * Organic Spacing: Cluster (8px), Group (16px), Section (32px) for natural rhythm
 */

import { tokens } from '@/design-system';

export const styles = {
  player: {
    display: 'flex',
    flexDirection: 'column' as const,
    width: '100%',

    // Glass effect for PlayerBar - semi-transparent for starfield visibility
    background: 'rgba(16, 23, 41, 0.50)',                 // 50% opacity for starfield visibility
    backdropFilter: 'blur(10px) saturate(1.08)',          // Moderate blur preserves starfield
    border: 'none',
    // Glass bevel: top highlight + outer shadow
    boxShadow: `0 -8px 32px ${tokens.colors.opacityScale.dark.standard}, inset 0 1px 0 rgba(255, 255, 255, 0.10)`,

    zIndex: tokens.zIndex.dropdown,
    padding: 0,
    gap: 0,
  },

  progressBarContainer: {
    width: '100%',
    height: 'auto',
    padding: `${tokens.spacing.cluster} ${tokens.spacing.lg}`,  // 8px top, organic spacing
    paddingBottom: tokens.spacing.xs,
  },

  mainRow: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: tokens.spacing.group,                            // 16px - organic group spacing
    padding: `${tokens.spacing.md} ${tokens.spacing.lg}`,
    minHeight: '64px',

    [`@media (max-width: ${tokens.breakpoints.md})`]: {
      flexDirection: 'column' as const,
      alignItems: 'stretch',
      padding: tokens.spacing.md,
      minHeight: 'auto',
      gap: tokens.spacing.md,
    },
  },

  trackInfoSection: {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacing.md,
    minWidth: '200px',
    flex: '1 1 auto',

    [`@media (max-width: ${tokens.breakpoints.md})`]: {
      minWidth: 'auto',
      width: '100%',
    },
  },

  rightSection: {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacing.md,
    flex: '1 1 auto',
    justifyContent: 'flex-end',

    [`@media (max-width: ${tokens.breakpoints.md})`]: {
      width: '100%',
      justifyContent: 'space-between',
    },
  },

  queueButton: {
    width: '40px',
    height: '40px',
    padding: 0,

    // Glass effect for queue button (idle state)
    background: 'transparent',
    border: tokens.glass.subtle.border,                   // Subtle glass border
    borderRadius: tokens.borderRadius.md,                 // 12px - softer, more organic

    cursor: 'pointer',
    fontSize: tokens.typography.fontSize.lg,              // 20px for impact
    fontWeight: tokens.typography.fontWeight.medium,
    transition: `${tokens.transitions.base}, backdrop-filter ${tokens.transitions.base}`,
    color: tokens.colors.text.primary,
    outline: 'none',
    // WCAG 2.4.7: visible focus ring for keyboard navigation (#2801)
    '&:focus-visible': {
      outline: `2px solid ${tokens.colors.accent.primary}`,
      outlineOffset: '2px',
    },
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },

  queuePanelWrapper: {
    // Glass effect for expanded queue panel
    background: tokens.glass.subtle.background,           // Subtle glass background
    backdropFilter: tokens.glass.subtle.backdropFilter,   // 20px blur for consistency
    borderTop: tokens.glass.subtle.border,                // Subtle glass border separator
    boxShadow: tokens.glass.subtle.boxShadow,             // Depth + inner glow

    padding: tokens.spacing.lg,
    maxHeight: '400px',
    overflowY: 'auto' as const,
  },

  errorBanner: {
    display: 'flex',
    alignItems: 'center',
    padding: tokens.spacing.md,

    // Glass effect for error banner (strong presence)
    // Uses canonical #EF4444 = rgb(239, 68, 68) from tokens.colors.semantic.error
    background: 'rgba(239, 68, 68, 0.15)',                // Error tint with transparency
    backdropFilter: 'blur(20px) saturate(1.1)',           // Glass blur
    border: '1px solid rgba(239, 68, 68, 0.3)',           // Error border
    boxShadow: '0 4px 16px rgba(239, 68, 68, 0.2), 0 0 0 1px rgba(255, 255, 255, 0.05)',

    borderRadius: tokens.borderRadius.md,                 // 12px - softer curves
    margin: tokens.spacing.sm,
  },

  errorText: {
    color: tokens.colors.text.primary,
    fontSize: tokens.typography.fontSize.sm,
    fontWeight: tokens.typography.fontWeight.bold,
  },
};
