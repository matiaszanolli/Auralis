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
import { themeVars } from '@/theme/semanticTheme';

export const styles = {
  player: {
    display: 'flex',
    flexDirection: 'column' as const,
    width: '100%',

    background: themeVars.surfacePrimary,
    border: 'none',
    borderTop: `1px solid ${themeVars.borderDefault}`,
    boxShadow: themeVars.shadowRaised,

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

    background: 'transparent',
    border: `1px solid ${themeVars.borderDefault}`,
    borderRadius: tokens.borderRadius.md,                 // 12px - softer, more organic

    cursor: 'pointer',
    fontSize: tokens.typography.fontSize.lg,              // 20px for impact
    fontWeight: tokens.typography.fontWeight.medium,
    transition: `${tokens.transitions.base}, backdrop-filter ${tokens.transitions.base}`,
    color: themeVars.textPrimary,
    outline: 'none',
    // WCAG 2.4.7: visible focus ring for keyboard navigation (#2801)
    '&:focus-visible': {
      outline: `2px solid ${themeVars.accent}`,
      outlineOffset: '2px',
    },
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    '&:hover': {
      background: themeVars.accentSoft,
      borderColor: themeVars.borderStrong,
    },
  },

  queuePanelWrapper: {
    background: themeVars.surfacePrimary,
    borderTop: `1px solid ${themeVars.borderSubtle}`,
    padding: tokens.spacing.lg,
    maxHeight: '400px',
    overflowY: 'auto' as const,
  },

  errorBanner: {
    display: 'flex',
    alignItems: 'center',
    padding: tokens.spacing.md,

    // Glass effect for error banner (strong presence) — tokenized (#3980)
    background: themeVars.errorSoft,
    border: `1px solid ${themeVars.error}`,

    borderRadius: tokens.borderRadius.md,                 // 12px - softer curves
    margin: tokens.spacing.sm,
  },

  errorText: {
    color: themeVars.textPrimary,
    fontSize: tokens.typography.fontSize.sm,
    fontWeight: tokens.typography.fontWeight.bold,
  },
};
