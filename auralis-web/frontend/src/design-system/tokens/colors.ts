/**
 * Auralis Design System Tokens — see ./README or tokens barrel.
 * Split from the former monolithic tokens.ts (#4079). Do not add cross-category
 * references here; each category is self-contained and merged in the barrel.
 * Within this file, the brand accent's rgba variants derive from its one hex (#6646).
 */

import { withOpacity } from './with-opacity';

const ACCENT_PRIMARY = '#7366F0';


  /**
   * Color System (Style Guide §1)
   * Color is stateful and atmospheric, not decorative.
   *
   * Rules:
   * - Color represents behavior, not categories
   * - Color is rarely solid
   * - Light and glow matter more than hue
   * - Saturation increases only when music is active
   *
   * "If a color feels 'loud' when nothing is playing, it's wrong."
   *
   * Base: Deep blue-black (#0B1020 range) - no pure black, no flat gray
   * The background should feel like a dark studio room, not a void.
   */
export const colors = {
    // Background colors (Deep blue-black - Design Language §2.1)
    bg: {
      level0: '#0B1020',       // Deep blue-black (canonical base)
      level1: '#101729',       // Slightly lifted navy (+4–8% luminance)
      level2: '#151D2F',       // Surfaces (subtle lift)
      level3: '#1A2338',       // Raised elements (cards as surfaces)
      level4: '#1F2940',       // Modals, overlays
    },

    // Brand colors (Soft Violet + Teal/Cyan + Warm Amber)
    accent: {
      primary: ACCENT_PRIMARY, // Soft Violet/Indigo - primary brand accent
      secondary: '#47D6FF',    // Teal/Cyan - audio state (Design Language §2.1)
      tertiary: '#C1C8EF',     // Lavender Smoke - secondary text
      energy: '#F59E0B',       // Warm Amber - transients/highlights (Design Language §2.1)
      // Light/dark variants of the brand accents (#3949). Used for the MUI
      // palette light/dark shades (auto hover/focus) so they stay token-backed
      // instead of hand-tuned hex in themeConfig.ts.
      primaryLight: '#8B7CF7',   // lighter tint of primary
      primaryDark: '#5A5CC4',    // darker shade of primary (also the aurora end stop)
      secondaryLight: '#6FE0FF', // lighter tint of secondary
      secondaryDark: '#00BCC4',  // darker shade of secondary
    },

    // Semantic accent colors (UI feedback states)
    semantic: {
      success: '#10B981',      // Success (positive)
      warning: '#F59E0B',      // Warning (caution)
      error: '#EF4444',        // Error (critical): text/icon/border colour, 3.5:1 against white - NOT a text-bearing fill
      errorFill: '#DC2626',    // Fill behind white text (danger buttons, banners): 4.83:1 (#6073)
      errorFillHover: '#B91C1C', // Its hover/active state, darker instead of translucent: 6.5:1
      info: '#3B82F6',         // Info (informational)
    },

    /**
     * Audio-Semantic Accent Colors (Style Guide §1.3)
     * Colors represent behavior and audio characteristics, not categories.
     * Usage: Never more than 2 accents in the same component.
     * Accents fade in/out with state. Glow > fill.
     */
    audioSemantic: {
      // Indigo/Violet - Identity, focus, playback (primary brand)
      identity: ACCENT_PRIMARY,

      // Cyan/Teal - Spatial width, clarity, stereo field
      spatial: '#47D6FF',

      // Magenta/Pink - Harmonic richness, vibrancy
      harmonic: '#EC4899',
    },

    /**
     * Text Colors (Style Guide §3.3)
     * Hierarchy via size, spacing, weight, and opacity - never color alone.
     * Text should sit in space, not scream.
     */
    text: {
      // Primary text: 90-100% opacity (titles, emphasis)
      primary: 'rgba(255, 255, 255, 0.95)',
      primaryFull: '#FFFFFF',  // 100% for maximum emphasis only

      // Secondary text: 60-70% opacity (labels, descriptions)
      secondary: 'rgba(255, 255, 255, 0.68)',

      // Metadata text: ≥60% opacity for WCAG AA 4.5:1 against bg.level1 (#2803)
      metadata: 'rgba(255, 255, 255, 0.60)',

      // Disabled text: ≥40% opacity for WCAG AA 3:1 large-text minimum (#2803)
      disabled: 'rgba(255, 255, 255, 0.40)',

      // Semantic aliases — actively used across primitives/components. Auralis
      // is desktop-only with no external token consumers, so these are internal
      // convenience names, not backwards-compat shims (#4402).
      tertiary: 'rgba(255, 255, 255, 0.60)',  // Maps to metadata
      muted: 'rgba(255, 255, 255, 0.50)',     // Between metadata and disabled
    },

    // Border colors (using soft opacity + brand colors)
    border: {
      light: withOpacity(ACCENT_PRIMARY, '0.12'),   // Subtle borders (soft violet)
      medium: withOpacity(ACCENT_PRIMARY, '0.24'),  // Standard borders
      heavy: withOpacity(ACCENT_PRIMARY, '0.40'),   // Emphasized borders
      accent: ACCENT_PRIMARY,                       // Accent borders (soft violet)
    },

    /**
     * Opacity Scales (Style Guide §1)
     * Standardized opacity levels for consistent UI layering.
     * Replaces Color.styles.ts opacity presets.
     */
    opacityScale: {
      // Accent color (soft violet #7366F0) with opacity variants
      accent: {
        minimal: withOpacity(ACCENT_PRIMARY, '0.05'),    // Barely visible, disabled states
        ultraLight: withOpacity(ACCENT_PRIMARY, '0.08'), // Very subtle backgrounds
        veryLight: withOpacity(ACCENT_PRIMARY, '0.10'),  // Light borders, subtle backgrounds
        light: withOpacity(ACCENT_PRIMARY, '0.12'),      // Track current state, soft hover
        lighter: withOpacity(ACCENT_PRIMARY, '0.15'),    // Hover states, gentle glows
        standard: withOpacity(ACCENT_PRIMARY, '0.20'),   // Standard backgrounds
        strong: withOpacity(ACCENT_PRIMARY, '0.30'),     // Focus states, button shadows
        veryStrong: withOpacity(ACCENT_PRIMARY, '0.40'), // Strong glows, prominent shadows
        intense: withOpacity(ACCENT_PRIMARY, '0.60'),    // High emphasis
        vivid: withOpacity(ACCENT_PRIMARY, '0.80'),      // Near-solid
        full: withOpacity(ACCENT_PRIMARY, '1.0'),        // Solid accent
      },

      // White with opacity (for light overlays, glass effects)
      white: {
        ultraLight: 'rgba(255, 255, 255, 0.03)',   // #3981 — below veryLight
        micro: 'rgba(255, 255, 255, 0.04)',        // #3981
        faint: 'rgba(255, 255, 255, 0.06)',        // #3981
        subtle: 'rgba(255, 255, 255, 0.08)',       // #3981
        light: 'rgba(255, 255, 255, 0.10)',
        lighter: 'rgba(255, 255, 255, 0.15)',
        strong: 'rgba(255, 255, 255, 0.30)',
        veryStrong: 'rgba(255, 255, 255, 0.50)',
      },

      // Deep blue-black with opacity (Style Guide: NO pure black)
      // Uses #0B1020 base instead of #000000
      dark: {
        veryLight: 'rgba(11, 16, 32, 0.05)',
        light: 'rgba(11, 16, 32, 0.10)',
        lighter: 'rgba(11, 16, 32, 0.15)',
        standard: 'rgba(11, 16, 32, 0.20)',
        strong: 'rgba(11, 16, 32, 0.30)',
        veryStrong: 'rgba(11, 16, 32, 0.40)',
        intense: 'rgba(11, 16, 32, 0.50)',
        nearOpaque: 'rgba(11, 16, 32, 0.80)',
      },
    },

    /**
     * Status Colors (for connection indicators, alerts)
     * Maps to semantic colors but with specific use cases.
     */
    status: {
      connected: '#10B981',    // Green - active/successful
      connecting: '#F59E0B',   // Amber - pending/loading
      disconnected: '#EF4444', // Red - error/offline
    },

    /**
     * Utility Color Presets (common patterns)
     * Ready-to-use color combinations for typical UI states.
     */
    utility: {
      // Destructive actions
      errorBg: 'rgba(239, 68, 68, 0.10)',
    },

    // #5646: the `export` palettes (#3596 — resolved colors for hypothetical
    // server-side analysis PNG/SVG rendering) are gone: nothing in the
    // frontend, backend or analysis engine ever consumed them.

    /**
     * Light-mode palette (#3597)
     * Resolved values for the optional light theme. Semantic colors share
     * hue with the dark mode (`semantic.*`) so a component showing the
     * same state has the same identity across themes — only neutrals and
     * surface lifts differ. Neon variants are dimmed for contrast against
     * a near-white canvas.
     */
    lightMode: {
      background: {
        primary: '#F8F9FD',
        secondary: '#FFFFFF',
        surface: '#FAFBFF',
        hover: '#F0F2F8',
        glass: 'rgba(255, 255, 255, 0.7)',
      },
      text: {
        primary: '#1A1F3A',
        secondary: '#5A6280',
        disabled: '#9CA3B8',
        accent: '#5B4FD6',     // accent as text: 5.65:1 on #F8F9FD (the brand #7366F0 is 4.08:1) (#5675)
      },
      // Unfilled rails, switch tracks and scrollbar thumbs: >= 3:1 against both the canvas and white (WCAG 1.4.11, #6021).
      controlTrack: '#8A90A6',
      // Darker than semantic.* on purpose: these colour TEXT on the near-white canvas, where the dark-mode
      // hexes were 2.0-3.6:1. Each is >= 4.5:1 on #F8F9FD and on #FFFFFF (#5675).
      accent: {
        success: '#047857',     // semantic.success, darkened: 5.2:1
        error: '#DC2626',       // semantic.error, darkened: 4.6:1
        warning: '#B45309',     // semantic.warning, darkened: 4.8:1
        info: '#3B82F6',        // matches semantic.info
      },
    },
} as const;
