/**
 * Color Styles - COMPATIBILITY LAYER
 *
 * @deprecated This file is deprecated. Import directly from '@/design-system' instead.
 *
 * This file re-exports values from the centralized design system tokens
 * for backwards compatibility. All new code should import from '@/design-system'.
 *
 * Migration guide:
 * - auroraOpacity → tokens.colors.opacityScale.accent
 * - whiteOpacity → tokens.colors.opacityScale.white
 * - blackOpacity → tokens.colors.opacityScale.dark (uses deep blue-black, not pure black)
 * - colorAuroraPrimary → tokens.colors.accent.primary
 * - colorAuroraSecondary → tokens.colors.accent.primary (secondary is now tertiary in tokens)
 * - gradients/gradientPresets → tokens.gradients.decorative
 * - statusColors → tokens.colors.status
 */

import { tokens } from '@/design-system';

// Re-export primary accent color
export const colorAuroraPrimary = tokens.colors.accent.primary;

// Secondary maps to accent primary (the old secondary #764ba2 is deprecated)
export const colorAuroraSecondary = tokens.colors.accent.primary;

/**
 * Aurora opacity scale (maps to tokens.colors.opacityScale.accent)
 * @deprecated Use tokens.colors.opacityScale.accent instead
 */
export const auroraOpacity = tokens.colors.opacityScale.accent;

/**
 * White opacity scale (maps to tokens.colors.opacityScale.white)
 * @deprecated Use tokens.colors.opacityScale.white instead
 */
export const whiteOpacity = tokens.colors.opacityScale.white;

/**
 * Dark opacity scale - uses deep blue-black (#0B1020), NOT pure black
 * Style Guide: "No pure black. No flat gray."
 * @deprecated Use tokens.colors.opacityScale.dark instead
 */
export const blackOpacity = tokens.colors.opacityScale.dark;

/**
 * Gradient presets (maps to tokens.gradients.decorative)
 * @deprecated Use tokens.gradients directly instead
 */
export const gradientPresets = {
  // Main aurora gradient
  aurora: tokens.gradients.aurora,
  aurora45: tokens.gradients.aurora.replace('135deg', '45deg'),
  auroraHover: tokens.gradients.aurora,

  // Decorative gradients
  neonSunset: tokens.gradients.decorative.neonSunset,
  deepOcean: tokens.gradients.decorative.deepOcean,
  electricPurple: tokens.gradients.decorative.electricPurple,
  cosmicBlue: tokens.gradients.decorative.cosmicBlue,
  gradientPink: tokens.gradients.decorative.gradientPink,
  gradientBlue: tokens.gradients.decorative.gradientBlue,
  gradientGreen: tokens.gradients.decorative.gradientGreen,
  gradientSunset: tokens.gradients.decorative.gradientSunset,
  gradientTeal: tokens.gradients.decorative.gradientTeal,
  gradientPastel: tokens.gradients.decorative.gradientPastel,
  gradientRose: tokens.gradients.decorative.gradientRose,

  // Overlay gradients
  bottomFade: tokens.gradients.overlay.bottomFade,
};

/**
 * Alias for gradientPresets
 * @deprecated Use tokens.gradients directly instead
 */
export const gradients = gradientPresets;

/**
 * Status colors (maps to tokens.colors.status)
 * @deprecated Use tokens.colors.status instead
 */
export const statusColors = {
  connected: tokens.colors.status.connected,
  connecting: tokens.colors.status.connecting,
  disconnected: tokens.colors.status.disconnected,
  success: tokens.colors.semantic.success,
  warning: tokens.colors.semantic.warning,
  error: tokens.colors.semantic.error,
  info: tokens.colors.semantic.info,
};

/**
 * Utility color presets (maps to tokens.colors.utility)
 * @deprecated Use tokens.colors.utility instead
 */
export const colorUtility = {
  border: {
    subtle: tokens.colors.opacityScale.accent.veryLight,
    standard: tokens.colors.opacityScale.accent.light,
    strong: tokens.colors.opacityScale.accent.lighter,
  },
  background: {
    hover: tokens.colors.opacityScale.accent.ultraLight,
    subtle: tokens.colors.opacityScale.accent.veryLight,
    standard: tokens.colors.opacityScale.accent.light,
    strong: tokens.colors.opacityScale.accent.standard,
  },
  focus: {
    ring: tokens.colors.opacityScale.accent.veryLight,
    glow: tokens.colors.opacityScale.accent.strong,
    glowStrong: tokens.colors.opacityScale.accent.veryStrong,
  },
  shadow: {
    subtle: tokens.colors.opacityScale.accent.light,
    standard: tokens.colors.opacityScale.accent.standard,
    strong: tokens.colors.opacityScale.accent.strong,
    veryStrong: tokens.colors.opacityScale.accent.veryStrong,
  },
  button: {
    hover: tokens.colors.opacityScale.accent.ultraLight,
    active: tokens.colors.opacityScale.accent.standard,
    disabled: tokens.colors.opacityScale.accent.minimal,
  },
  error: tokens.colors.utility.error,
  errorHover: tokens.colors.utility.errorHover,
  success: tokens.colors.semantic.success,
  successHover: tokens.colors.audioSemantic.stability,
  warning: tokens.colors.semantic.warning,
  warningHover: tokens.colors.accent.energy,
};

/**
 * Color combinations for common patterns
 * @deprecated Use tokens.colors.utility instead
 */
export const colorCombos = {
  hoverState: {
    background: tokens.colors.opacityScale.accent.ultraLight,
    text: tokens.colors.accent.primary,
  },
  activeState: {
    background: tokens.colors.opacityScale.accent.standard,
    text: tokens.colors.text.primaryFull,
  },
  focusRing: {
    ring: tokens.colors.utility.focusRing,
    glow: tokens.colors.utility.focusGlow,
  },
  disabledState: {
    background: tokens.colors.opacityScale.accent.minimal,
    text: tokens.colors.text.disabled,
  },
};
