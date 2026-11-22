/**
 * Auralis Design System Tokens — see ./README or tokens barrel.
 * Split from the former monolithic tokens.ts (#4079). Each category is merged in the barrel; the
 * glows read their colour from the colors category instead of re-spelling its channels (#6646).
 */

import { colors } from './colors';
import { withOpacity } from './with-opacity';


  /**
   * Shadow System (Ambient opacity - no harsh black)
   * Elevation levels + audio-reactive glows
   */
export const shadows = {
    none: 'none',

    // Elevation shadows (ambient opacity for depth)
    sm: '0 2px 4px rgba(0, 0, 0, 0.08)',
    md: '0 4px 12px rgba(0, 0, 0, 0.16)',         // Card shadow (elevation 1)
    lg: '0 8px 24px rgba(0, 0, 0, 0.20)',        // Raised panel (elevation 2)
    xl: '0 12px 32px rgba(0, 0, 0, 0.28)',       // Modal (elevation 3)
    '2xl': '0 16px 40px rgba(0, 0, 0, 0.32)',    // Top-level (elevation 4)

    // Glow shadows (audio-reactive elements)
    glowSoft: `0 0 16px ${withOpacity(colors.accent.primary, '0.20')}`, // Soft violet glow
    glowMd: `0 0 24px ${withOpacity(colors.accent.primary, '0.32')}`,   // Violet glow (medium)
} as const;

  /**
   * Transition System (smooth, intentional animations)
   */
  /**
   * Motion Language (Style Guide §6)
   * Motion in Auralis is: Slow, Weighted, Predictable, Purposeful.
   * "If motion draws attention to itself, it's wrong."
   *
   * Timing Guidelines:
   * - Hover: 120–180ms
   * - State changes: 300–600ms
   * - Audio-reactive: Lag audio by ~80–120ms
   *
   * Forbidden:
   * - No fast oscillations
   * - No bounce easing
   */
export const transitions = {
    // Durations (Style Guide §6.2)
    hover: '150ms',      // Hover states: 120–180ms
    stateChange: '450ms', // State changes: 300–600ms (middle of range)
    slow: '600ms',       // Slower state changes
    audioLag: '100ms',   // Audio-reactive lag: 80–120ms (middle of range)

    // Semantic duration aliases — actively used across components. Internal
    // convenience names (desktop-only app, no external consumers), not
    // backwards-compat shims (#4402).
    fast: '150ms',
    base: '450ms',

    // Easing functions (slow, heavy, analog - NO BOUNCE)
    easeOut: 'cubic-bezier(0.25, 0.46, 0.45, 0.94)',    // Fluid deceleration
    easeInOut: 'cubic-bezier(0.4, 0, 0.6, 1)',          // Natural, weighted

    // Combined (duration + easing) - Motion feels inevitable
    hover_out: '150ms cubic-bezier(0.25, 0.46, 0.45, 0.94)',
    state_inOut: '450ms cubic-bezier(0.4, 0, 0.6, 1)',
    slow_inOut: '600ms cubic-bezier(0.4, 0, 0.6, 1)',

    // Semantic combined aliases — actively used (e.g. ThemeToggle, ContextMenu,
    // EmptyState). Internal convenience names, not backwards-compat shims (#4402).
    base_inOut: '450ms cubic-bezier(0.4, 0, 0.6, 1)',

    // Property-specific
    color: '450ms color cubic-bezier(0.4, 0, 0.6, 1)',
    background: '450ms background-color cubic-bezier(0.4, 0, 0.6, 1)',
    transform: '600ms transform cubic-bezier(0.25, 0.1, 0.25, 1)',
    opacity: '450ms opacity cubic-bezier(0.4, 0, 0.6, 1)',
    all: '450ms all cubic-bezier(0.4, 0, 0.6, 1)',
} as const;

  /**
   * Animation System
   */
export const animations = {
    pulse: {
      duration: '2s',
      timing: 'ease-in-out',
      iteration: 'infinite',
    },
} as const;
