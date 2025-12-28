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
   * Primary button styling (Play/Pause) - Design Language v1.2.0
   * - Circular 56px button (design spec: audio parameter thumb)
   * - Aurora gradient (Soft Violet → darker)
   * - Glass effect on hover for elevated aesthetic
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
    fontSize: tokens.typography.fontSize.xl,             // 24px for visual impact
    fontWeight: tokens.typography.fontWeight.bold,
    color: tokens.colors.text.primary,
    transition: `${tokens.transitions.all}, backdrop-filter ${tokens.transitions.base}`,

    // Enhanced shadow for depth + inner glow
    boxShadow: '0 8px 24px rgba(115, 102, 240, 0.3), 0 0 0 1px rgba(255, 255, 255, 0.08)',
    outline: 'none',

    // Glass effect on hover (elevated state)
    '&:hover:not(:disabled)': {
      transform: 'scale(1.05)',                           // Subtle scale for organic feel
      boxShadow: '0 12px 32px rgba(115, 102, 240, 0.4), 0 0 0 1px rgba(255, 255, 255, 0.12)',
    },

    '&:active:not(:disabled)': {
      transform: 'scale(0.98)',                           // Press feedback
      boxShadow: '0 4px 16px rgba(115, 102, 240, 0.5), 0 0 0 1px rgba(255, 255, 255, 0.15)',
    },

    ':disabled': {
      opacity: 0.5,
      cursor: 'not-allowed',
    },
  },

  /**
   * Secondary button styling (Next/Previous) - Design Language v1.2.0
   * - Compact 40px square
   * - Ghost style (transparent background, soft border)
   * - Glass effect on hover for elevated aesthetic
   * - Hover: glass background + subtle glow
   */
  secondaryButton: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: '40px',
    height: '40px',
    padding: 0,
    backgroundColor: 'transparent',
    border: tokens.glass.subtle.border,                   // Subtle glass border (10% white opacity)
    borderRadius: tokens.borderRadius.md,                 // 12px - softer, more organic
    cursor: 'pointer',
    fontSize: tokens.typography.fontSize.md,              // 15px
    color: tokens.colors.text.primary,
    transition: `${tokens.transitions.all}, backdrop-filter ${tokens.transitions.base}`,
    outline: 'none',

    // Glass effect on hover
    '&:hover:not(:disabled)': {
      background: tokens.glass.subtle.background,         // Subtle glass background
      backdropFilter: tokens.glass.subtle.backdropFilter, // 20px blur for glossy effect
      border: tokens.glass.subtle.border,
      boxShadow: tokens.glass.subtle.boxShadow,           // Depth + inner glow
      transform: 'translateY(-2px)',                      // Subtle lift for organic feel
    },

    '&:active:not(:disabled)': {
      transform: 'translateY(0px)',                       // Press feedback
      boxShadow: '0 2px 8px rgba(0, 0, 0, 0.1)',
    },

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
