/**
 * PlaybackControls Styles
 * ~~~~~~~~~~~~~~~~~~~~~~~
 * Centralized styles for playback control buttons using design tokens.
 * Provides modern button styling with proper visual hierarchy.
 */

import { tokens } from '@/design-system';

const styles = {
  /**
   * Container for all control buttons - compact footer layout
   */
  container: {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacing.md,
    justifyContent: 'center',
    flex: '0 0 auto',
  },

  /**
   * Primary button styling (Play/Pause)
   * - Compact size for footer bar (48px)
   * - Gradient background
   * - Subtle glow on hover
   */
  primaryButton: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: '48px',
    height: '48px',
    padding: 0,
    background: `linear-gradient(135deg, ${tokens.colors.accent.primary} 0%, ${tokens.colors.accent.secondary} 100%)`,
    border: `1px solid ${tokens.colors.accent.primary}`,
    borderRadius: tokens.borderRadius.md,
    cursor: 'pointer',
    fontSize: tokens.typography.fontSize.xl,
    fontWeight: tokens.typography.fontWeight.bold,
    color: tokens.colors.text.primary,
    transition: `all ${tokens.transitions.base}`,
    boxShadow: tokens.shadows.sm,
    outline: 'none',

    ':disabled': {
      opacity: 0.5,
      cursor: 'not-allowed',
    },
  },

  /**
   * Secondary button styling (Next/Previous)
   * - Compact, minimal design
   * - Transparent with subtle border
   */
  secondaryButton: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: '40px',
    height: '40px',
    padding: 0,
    backgroundColor: 'transparent',
    border: `1px solid ${tokens.colors.border.medium}`,
    borderRadius: tokens.borderRadius.md,
    cursor: 'pointer',
    fontSize: tokens.typography.fontSize.md,
    color: tokens.colors.text.primary,
    transition: `all ${tokens.transitions.base}`,
    outline: 'none',

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
    marginLeft: tokens.spacing.sm,
    fontStyle: 'italic',
  },
};

export default styles;
