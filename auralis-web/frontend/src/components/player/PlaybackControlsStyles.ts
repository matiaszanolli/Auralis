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
   * - Circular 56px button (design spec: audio parameter thumb)
   * - Aurora gradient (Soft Violet → darker)
   * - Subtle glow on hover, intense on active
   */
  primaryButton: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: '56px',
    height: '56px',
    padding: 0,
    background: tokens.gradients.aurora,
    border: 'none',
    borderRadius: tokens.borderRadius.full,
    cursor: 'pointer',
    fontSize: tokens.typography.fontSize.xl,
    fontWeight: tokens.typography.fontWeight.bold,
    color: tokens.colors.text.primary,
    transition: tokens.transitions.all,
    boxShadow: tokens.shadows.md,
    outline: 'none',

    ':disabled': {
      opacity: 0.5,
      cursor: 'not-allowed',
    },
  },

  /**
   * Secondary button styling (Next/Previous)
   * - Compact 40px square
   * - Ghost style (transparent background, soft border)
   * - Hover: bg tint + accent border
   */
  secondaryButton: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: '40px',
    height: '40px',
    padding: 0,
    backgroundColor: 'transparent',
    border: `1px solid ${tokens.colors.border.light}`,
    borderRadius: tokens.borderRadius.md,
    cursor: 'pointer',
    fontSize: tokens.typography.fontSize.md,
    color: tokens.colors.text.primary,
    transition: tokens.transitions.all,
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
