/**
 * Auralis Design System Tokens — see ./README or tokens barrel.
 * Split from the former monolithic tokens.ts (#4079). Do not add cross-category
 * references here; each category is self-contained and merged in the barrel.
 */


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
      // Backwards compatibility
      primary: '#0B1020',
      secondary: '#101729',
      tertiary: '#151D2F',
      elevated: '#1A2338',
      overlay: 'rgba(11, 16, 32, 0.95)',
    },

    // Brand colors (Soft Violet + Teal/Cyan + Warm Amber)
    accent: {
      primary: '#7366F0',      // Soft Violet/Indigo - primary brand accent
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
      error: '#EF4444',        // Error (critical)
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
      identity: '#7366F0',
      identityGlow: 'rgba(115, 102, 240, 0.4)',

      // Cyan/Teal - Spatial width, clarity, stereo field
      spatial: '#47D6FF',
      spatialGlow: 'rgba(71, 214, 255, 0.4)',

      // Green - Energy stability, balance, dynamics
      stability: '#10B981',
      stabilityGlow: 'rgba(16, 185, 129, 0.4)',

      // Amber/Warm - Transients, intensity, peaks
      transient: '#F59E0B',
      transientGlow: 'rgba(245, 158, 11, 0.4)',

      // Magenta/Pink - Harmonic richness, vibrancy
      harmonic: '#EC4899',
      harmonicGlow: 'rgba(236, 72, 153, 0.4)',
      // Darkened harmonic accent (#3949) — the dark-mode neon purple/magenta,
      // kept distinct from the brand violet. Was a magic hex in themeConfig.ts.
      harmonicDark: '#C44569',
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

      // Legacy aliases (for backwards compatibility)
      tertiary: 'rgba(255, 255, 255, 0.60)',  // Maps to metadata
      muted: 'rgba(255, 255, 255, 0.50)',     // Between metadata and disabled

      // Inverse (for light backgrounds)
      inverse: '#0D111A',
    },

    // Border colors (using soft opacity + brand colors)
    border: {
      light: 'rgba(115, 102, 240, 0.12)',   // Subtle borders (soft violet)
      medium: 'rgba(115, 102, 240, 0.24)',  // Standard borders
      heavy: 'rgba(115, 102, 240, 0.40)',   // Emphasized borders
      accent: '#7366F0',                     // Accent borders (soft violet)
    },

    /**
     * Opacity Scales (Style Guide §1)
     * Standardized opacity levels for consistent UI layering.
     * Replaces Color.styles.ts opacity presets.
     */
    opacityScale: {
      // Accent color (soft violet #7366F0) with opacity variants
      accent: {
        minimal: 'rgba(115, 102, 240, 0.05)',    // Barely visible, disabled states
        ultraLight: 'rgba(115, 102, 240, 0.08)', // Very subtle backgrounds
        veryLight: 'rgba(115, 102, 240, 0.10)',  // Light borders, subtle backgrounds
        light: 'rgba(115, 102, 240, 0.12)',      // Track current state, soft hover
        lighter: 'rgba(115, 102, 240, 0.15)',    // Hover states, gentle glows
        standard: 'rgba(115, 102, 240, 0.20)',   // Standard backgrounds
        strong: 'rgba(115, 102, 240, 0.30)',     // Focus states, button shadows
        veryStrong: 'rgba(115, 102, 240, 0.40)', // Strong glows, prominent shadows
        intense: 'rgba(115, 102, 240, 0.60)',    // High emphasis
        vivid: 'rgba(115, 102, 240, 0.80)',      // Near-solid
        full: 'rgba(115, 102, 240, 1.0)',        // Solid accent
      },

      // White with opacity (for light overlays, glass effects)
      white: {
        ultraLight: 'rgba(255, 255, 255, 0.03)',   // #3981 — below veryLight
        micro: 'rgba(255, 255, 255, 0.04)',        // #3981
        faint: 'rgba(255, 255, 255, 0.06)',        // #3981
        subtle: 'rgba(255, 255, 255, 0.08)',       // #3981
        veryLight: 'rgba(255, 255, 255, 0.05)',
        light: 'rgba(255, 255, 255, 0.10)',
        lighter: 'rgba(255, 255, 255, 0.15)',
        standard: 'rgba(255, 255, 255, 0.20)',
        strong: 'rgba(255, 255, 255, 0.30)',
        veryStrong: 'rgba(255, 255, 255, 0.50)',
        nearOpaque: 'rgba(255, 255, 255, 0.70)',
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
      // Hover/active backgrounds
      hoverBg: 'rgba(115, 102, 240, 0.08)',
      activeBg: 'rgba(115, 102, 240, 0.20)',
      disabledBg: 'rgba(115, 102, 240, 0.05)',

      // Focus rings and glows
      focusRing: '0 0 0 3px rgba(115, 102, 240, 0.10)',
      focusGlow: '0 0 12px rgba(115, 102, 240, 0.30)',

      // Destructive actions
      error: '#EF4444',
      errorHover: '#DC2626',
      errorBg: 'rgba(239, 68, 68, 0.10)',
      errorBgMedium: 'rgba(239, 68, 68, 0.15)',   // stronger error tint (#3980)
      errorBorder: 'rgba(239, 68, 68, 0.30)',     // error banner border (#3980)
      errorGlow: 'rgba(239, 68, 68, 0.20)',       // error banner box-shadow tint (#3980)

      // Success backgrounds
      successBg: 'rgba(16, 185, 129, 0.10)',
    },

    /**
     * Export Palettes (#3596)
     * Resolved colors for analysis exports (PNG/SVG/Canvas) where the
     * runtime DOM is not available. Both palettes derive from semantic
     * tokens — no off-brand cyan, amber or pure black.
     *
     * - dark: deep blue-black canvas background (Style Guide §1 — no
     *   pure black), primary text full white, primary stroke maps to
     *   brand violet, secondaries map to spatial/transient accents.
     * - light: paper white background with darkened brand variants for
     *   sufficient contrast against light surfaces.
     */
    export: {
      dark: {
        text: '#FFFFFF',
        background: '#0B1020',  // bg.level0 — deep blue-black
        border: 'rgba(255, 255, 255, 0.15)',
        primary: '#7366F0',     // accent.primary (brand violet)
        secondary: '#47D6FF',   // accent.secondary (spatial cyan)
        danger: '#EF4444',      // semantic.error
        warning: '#F59E0B',     // semantic.warning
      },
      light: {
        text: '#0B1020',        // bg.level0 reused as ink
        background: '#FFFFFF',
        border: 'rgba(11, 16, 32, 0.15)',
        primary: '#5C4FD0',     // darkened brand violet for light bg contrast
        secondary: '#0E91B8',   // darkened cyan for light bg contrast
        danger: '#B91C1C',
        warning: '#B45309',
      },
    },

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
      },
      // Semantic colors aligned with dark mode (semantic.*)
      accent: {
        success: '#10B981',     // matches semantic.success
        error: '#EF4444',       // matches semantic.error
        warning: '#F59E0B',     // matches semantic.warning
        info: '#3B82F6',        // matches semantic.info
      },
      neon: {
        pink: '#D9577E',
        purple: '#A03D5A',
        blue: '#3B82F6',
        cyan: '#10B981',
        orange: '#F59E0B',
      },
    },
} as const;
