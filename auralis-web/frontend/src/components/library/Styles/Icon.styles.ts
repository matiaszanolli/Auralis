/**
 * Icon Styles - Reusable icon and icon button styling
 *
 * Consolidates icon sizing patterns and icon button variants used across
 * player controls, action buttons, and decorative icons.
 *
 * Icon Button Sizes:
 * - SmallIconButton: 32px (secondary actions, compact)
 * - MediumIconButton: 40px (standard list actions)
 * - LargeIconButton: 56px (primary player controls)
 *
 * Icon Sizes (for use with sx prop):
 * - xs: 16px (dense UI)
 * - sm: 20px (standard)
 * - md: 24px (medium)
 * - lg: 32px (large)
 * - xl: 48px (extra large)
 * - xxl: 64px (huge)
 */

// No exports - all icon styles consolidated into component-specific style files
//
// Consolidation Reference:
// - SmallIconButton (32px) → Inlined in TrackRow.styles.ts (PlayButton, MoreButton)
// - MediumIconButton (40px) → No longer needed after consolidation
// - LargeIconButton (56px) → No longer needed after consolidation
// - IconBox → No longer needed after consolidation
// - iconSizes → Replaced with direct sx prop usage in components

export {};
