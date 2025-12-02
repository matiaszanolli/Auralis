/**
 * PlaybackControls Styles
 * ~~~~~~~~~~~~~~~~~~~~~~~
 * Centralized styles for playback control buttons using design tokens.
 * Provides modern button styling with proper visual hierarchy.
 */

import { tokens } from '@/design-system';

const styles = {
  /**
   * Container for all control buttons
   */
  container: {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacing.lg,
    justifyContent: 'center',
  },

  /**
   * Primary button styling (Play/Pause)
   * - Larger size for emphasis
   * - Gradient background with glow effect
   * - Enhanced hover interactions
   */
  primaryButton: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: '56px',
    height: '56px',
    padding: 0,
    background: `linear-gradient(135deg, ${tokens.colors.accent.primary} 0%, ${tokens.colors.accent.secondary} 100%)`,
    border: `2px solid ${tokens.colors.accent.primary}`,
    borderRadius: tokens.borderRadius.lg,
    cursor: 'pointer',
    fontSize: tokens.typography.fontSize['2xl'],
    fontWeight: tokens.typography.fontWeight.bold,
    color: tokens.colors.text.primary,
    transition: `all ${tokens.transitions.base}`,
    boxShadow: tokens.shadows.glow,
    outline: 'none',

    // Disabled state
    ':disabled': {
      opacity: 0.5,
      cursor: 'not-allowed',
    },
  },

  /**
   * Secondary button styling (Next/Previous)
   * - Smaller size
   * - Subtle border styling
   * - Minimal visual weight
   */
  secondaryButton: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: '48px',
    height: '48px',
    padding: 0,
    backgroundColor: tokens.colors.bg.primary,
    border: `1.5px solid ${tokens.colors.border.medium}`,
    borderRadius: tokens.borderRadius.md,
    cursor: 'pointer',
    fontSize: tokens.typography.fontSize.lg,
    color: tokens.colors.text.primary,
    transition: `all ${tokens.transitions.base}`,
    outline: 'none',

    // Disabled state
    ':disabled': {
      opacity: 0.5,
      cursor: 'not-allowed',
    },
  },

  /**
   * Loading indicator text
   */
  loadingIndicator: {
    fontSize: tokens.typography.fontSize.xs,
    color: tokens.colors.text.secondary,
    marginLeft: tokens.spacing.md,
    fontStyle: 'italic',
  },
};

export default styles;
