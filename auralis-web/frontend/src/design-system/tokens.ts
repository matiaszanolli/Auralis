/**
 * Auralis Design System Tokens
 *
 * Single source of truth for all design values.
 * ALL components MUST use these tokens - no hardcoded values allowed.
 *
 * Core Philosophy (Style Guide §10):
 * "Every visual decision must either clarify the music or get out of its way."
 *
 * If an element does neither: Remove it, Hide it, or Demote it.
 *
 * @see docs/UI_STYLE_GUIDE.md - Full style guide documentation
 */

export const tokens = {
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
  colors: {
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

      // Metadata text: 40-50% opacity (timestamps, counts, technical info)
      metadata: 'rgba(255, 255, 255, 0.45)',

      // Disabled text: <30% opacity
      disabled: 'rgba(255, 255, 255, 0.25)',

      // Legacy aliases (for backwards compatibility)
      tertiary: 'rgba(255, 255, 255, 0.45)',  // Maps to metadata
      muted: 'rgba(255, 255, 255, 0.35)',     // Between metadata and disabled

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
    },
  },

  /**
   * Spacing System - Organic Rhythm (Design Language §4.2)
   * Variable spacing creates natural grouping and breathing room.
   * Tight within groups, generous between sections.
   */
  spacing: {
    // Micro spacing (within elements)
    xxs: '2px',      // Minimal gap, icon-text spacing
    xs: '4px',       // Tight spacing, related items
    sm: '6px',       // Small gap, form elements

    // Standard spacing (between elements)
    md: '12px',      // Medium gap, list items (reduced from 16px for tighter grouping)
    lg: '20px',      // Large gap, card padding (reduced from 24px)
    xl: '28px',      // Section spacing (reduced from 32px)

    // Macro spacing (between sections)
    xxl: '40px',     // Major section breaks (reduced from 48px)
    xxxl: '56px',    // Page-level spacing (reduced from 64px)
    xxxxl: '80px',   // Maximum breathing room (new)

    // Organic spacing (variable gaps)
    cluster: '8px',  // Items in natural clusters (library items, playlist tracks)
    group: '16px',   // Between groups within sections
    section: '32px', // Between major sections (Library, Playlists, Settings)
  },

  /**
   * Typography System (Design Language §3)
   * Inter (information, controls, metadata) + Manrope (identity, headers, track titles)
   * Typography should disappear when listening.
   */
  typography: {
    fontFamily: {
      primary: 'Inter, "Segoe UI", sans-serif',                                    // Information, controls, metadata
      header: 'Manrope, Arial, sans-serif',                                        // Identity, headers, track titles (sparingly)
      mono: "'JetBrains Mono', 'Courier New', monospace",                         // Technical readouts (dB, Hz, LUFS) - reveal on interaction only
      system: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif',
    },

    fontSize: {
      xs: '10px',      // Micro labels, timestamps (reduced for contrast)
      sm: '11px',      // Small text, metadata, captions (reduced)
      base: '13px',    // Standard body text (reduced for contrast)
      md: '15px',      // Larger body, input labels
      lg: '20px',      // Track titles, card headers (increased for impact)
      xl: '24px',      // Album titles, section headers (increased)
      '2xl': '28px',   // Page headers, artist names (increased)
      '3xl': '36px',   // Large headers, hero text (increased)
      '4xl': '56px',   // Display, hero text (increased for drama)
      '5xl': '72px',   // Ultra-large display (new for maximum impact)
    },

    fontWeight: {
      light: 300,      // Added for delicate text
      normal: 400,
      medium: 500,
      semibold: 600,
      bold: 700,
      extrabold: 800,  // Added for maximum impact headers
    },

    lineHeight: {
      tight: 1.2,      // Headers
      normal: 1.5,     // Body text
      relaxed: 1.75,   // Long-form
    },

    letterSpacing: {
      normal: '0',
      tight: '-0.01em',
      loose: '0.02em',
    },
  },

  /**
   * Border Radius System - Organic Curves (Design Language §4.4)
   * Softer, more generous curves create fluid, organic aesthetic.
   * Minimum 8px for any interactive element.
   */
  borderRadius: {
    none: '0',
    sm: '8px',       // Minimum for any rounded element (increased from 4px)
    md: '12px',      // Standard cards, buttons (increased from 8px)
    lg: '16px',      // Large cards, panels (increased from 12px)
    xl: '20px',      // Hero cards, modals (increased from 16px)
    '2xl': '24px',   // Maximum curve for rectangles (new)
    '3xl': '32px',   // Ultra-round for special elements (new)
    full: '9999px',  // Pill shape, circular buttons
  },

  /**
   * Shadow System (Ambient opacity - no harsh black)
   * Elevation levels + audio-reactive glows + glassmorphism depth
   */
  shadows: {
    none: 'none',

    // Elevation shadows (ambient opacity for depth)
    xs: '0 1px 2px rgba(0, 0, 0, 0.05)',
    sm: '0 2px 4px rgba(0, 0, 0, 0.08)',
    base: '0 2px 4px rgba(0, 0, 0, 0.10)',
    md: '0 4px 12px rgba(0, 0, 0, 0.16)',         // Card shadow (elevation 1)
    lg: '0 8px 24px rgba(0, 0, 0, 0.20)',        // Raised panel (elevation 2)
    xl: '0 12px 32px rgba(0, 0, 0, 0.28)',       // Modal (elevation 3)
    '2xl': '0 16px 40px rgba(0, 0, 0, 0.32)',    // Top-level (elevation 4)

    // Glow shadows (audio-reactive elements)
    glowSoft: '0 0 16px rgba(115, 102, 240, 0.20)',      // Soft violet glow
    glowMd: '0 0 24px rgba(115, 102, 240, 0.32)',        // Violet glow (medium)
    glowStrong: '0 0 32px rgba(115, 102, 240, 0.48)',    // Strong violet glow
    glowAqua: '0 0 20px rgba(71, 214, 255, 0.24)',       // Electric Aqua glow
    glowAquaIntense: '0 0 32px rgba(71, 214, 255, 0.40)', // Aqua glow (processing)
    glowAquaUltra: '0 0 48px rgba(71, 214, 255, 0.56)',  // Ultra aqua (active states)

    // Glass depth shadows (for glassmorphism layering)
    glassSubtle: '0 4px 16px rgba(0, 0, 0, 0.12), 0 0 0 1px rgba(255, 255, 255, 0.05)', // Glass surface
    glassMd: '0 8px 32px rgba(0, 0, 0, 0.18), 0 0 0 1px rgba(255, 255, 255, 0.08)',     // Elevated glass
    glassStrong: '0 16px 48px rgba(0, 0, 0, 0.24), 0 0 0 1px rgba(255, 255, 255, 0.12)', // Prominent glass
  },

  /**
   * Backdrop Blur System (Glassmorphism)
   * Premium translucent surfaces with background blur
   */
  blur: {
    none: 'none',
    xs: 'blur(4px)',
    sm: 'blur(8px)',
    md: 'blur(12px)',
    lg: 'blur(16px)',
    xl: 'blur(24px)',
    xxl: 'blur(32px)',
  },

  /**
   * Elevation System (UX Polish - Phase 4b)
   * Standardized depth patterns for consistent visual hierarchy
   *
   * Based on shadow-based depth (no hard borders) established in Phases 1-4a:
   * - Cards use resting + hover elevations
   * - Panels use separation shadows (left/right)
   * - Sections use subtle background differences + spacing
   */
  elevation: {
    // Card elevations (track cards, album cards)
    card: {
      resting: '0 2px 8px rgba(0, 0, 0, 0.15)',     // Subtle depth at rest
      hover: '0 8px 24px rgba(0, 0, 0, 0.25)',      // Clear elevation on hover
    },

    // Panel separations (sidebar, right panel)
    panel: {
      left: '-2px 0 16px rgba(0, 0, 0, 0.12)',      // Right panel (left shadow)
      right: '2px 0 16px rgba(0, 0, 0, 0.12)',      // Sidebar (right shadow)
    },

    // Section depth (internal components)
    section: {
      subtle: '0 1px 4px rgba(0, 0, 0, 0.08)',      // Very subtle separation
      medium: '0 2px 8px rgba(0, 0, 0, 0.12)',      // Medium depth
    },
  },

  /**
   * Opacity System (UX Polish - Phase 4b)
   * Standardized opacity levels for fading UI elements
   *
   * Based on fade patterns established in Phases 1-4a:
   * - Infrastructure elements (labels, dividers) fade more (~40-60%)
   * - Inactive content (icons, text) fade less (~15-30%)
   * - Duration badges and secondary UI fade moderately (~20-40%)
   */
  opacity: {
    // Infrastructure (should recede into background)
    infrastructure: {
      labels: 0.6,        // Section labels, dividers (~40% fade)
      dividers: 0.5,      // Dividers between sections (~50% fade)
    },

    // Inactive states (reduce prominence, not hide)
    inactive: {
      icons: 0.7,         // Inactive navigation icons (~30% fade)
      text: 0.75,         // Inactive navigation text (~25% fade)
      labels: 0.85,       // Parameter labels (~15% fade)
    },

    // Secondary UI elements
    secondary: {
      badges: 0.6,        // Duration badges at rest (~40% fade)
      headers: 0.8,       // Section headers (~20% fade)
    },

    // Active/visible states (full visibility)
    active: {
      full: 1.0,          // Active/important elements
      emphasized: 1.0,    // Emphasized content
    },
  },

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
  transitions: {
    // Durations (Style Guide §6.2)
    hover: '150ms',      // Hover states: 120–180ms
    stateChange: '450ms', // State changes: 300–600ms (middle of range)
    slow: '600ms',       // Slower state changes
    audioLag: '100ms',   // Audio-reactive lag: 80–120ms (middle of range)

    // Legacy aliases
    fast: '150ms',
    base: '450ms',
    verySlow: '600ms',

    // Easing functions (slow, heavy, analog - NO BOUNCE)
    easeOut: 'cubic-bezier(0.25, 0.46, 0.45, 0.94)',    // Fluid deceleration
    easeInOut: 'cubic-bezier(0.4, 0, 0.6, 1)',          // Natural, weighted
    easeSmooth: 'cubic-bezier(0.25, 0.1, 0.25, 1)',     // Slow, heavy, analog

    // Combined (duration + easing) - Motion feels inevitable
    hover_out: '150ms cubic-bezier(0.25, 0.46, 0.45, 0.94)',
    state_inOut: '450ms cubic-bezier(0.4, 0, 0.6, 1)',
    slow_inOut: '600ms cubic-bezier(0.4, 0, 0.6, 1)',

    // Legacy combined aliases
    fast_out: '150ms cubic-bezier(0.25, 0.46, 0.45, 0.94)',
    base_inOut: '450ms cubic-bezier(0.4, 0, 0.6, 1)',
    verySlow_inOut: '600ms cubic-bezier(0.25, 0.1, 0.25, 1)',

    // Property-specific
    color: '450ms color cubic-bezier(0.4, 0, 0.6, 1)',
    background: '450ms background-color cubic-bezier(0.4, 0, 0.6, 1)',
    transform: '600ms transform cubic-bezier(0.25, 0.1, 0.25, 1)',
    opacity: '450ms opacity cubic-bezier(0.4, 0, 0.6, 1)',
    all: '450ms all cubic-bezier(0.4, 0, 0.6, 1)',
  },

  /**
   * Audio-Reactive Motion (Style Guide §6.3)
   * Rules:
   * - Heavy smoothing
   * - No frame-perfect sync
   * - Motion represents trend, not sample data
   * - UI should feel like it's interpreting, not measuring
   */
  audioReactive: {
    // Timing
    lagMs: 100,           // Lag audio by 80-120ms (middle)
    lagMinMs: 80,         // Minimum lag
    lagMaxMs: 120,        // Maximum lag

    // Smoothing (heavy smoothing required)
    smoothingFactor: 0.85, // High smoothing (0 = none, 1 = max)
    decayRate: 0.92,       // Slow decay for trailing visuals

    // Update rate
    updateIntervalMs: 50,  // ~20fps max for visuals (not frame-perfect)

    // CSS transitions for audio-reactive elements
    transition: '100ms cubic-bezier(0.25, 0.1, 0.25, 1)',
    glowTransition: '150ms cubic-bezier(0.25, 0.1, 0.25, 1)',
  },

  /**
   * Numbers Policy (Style Guide §7.3)
   * Numbers exist, but are hidden by default.
   * Engineers can inspect. Listeners can listen.
   */
  numbersPolicy: {
    // Default visibility
    defaultVisibility: 'hidden',

    // Reveal behavior
    revealOn: 'interaction', // 'hover' | 'click' | 'interaction'
    revealTransition: '300ms cubic-bezier(0.4, 0, 0.6, 1)',

    // Hierarchy when visible
    hierarchy: 'secondary', // Numbers are never primary

    // Styling when revealed
    revealed: {
      opacity: 0.7,
      fontSize: '11px',
      fontFamily: "'JetBrains Mono', monospace",
    },
  },

  /**
   * Visualization Guidelines (Style Guide §7)
   * Visuals answer: "What is the music doing now?"
   * Not: "What are the numbers?"
   */
  visualization: {
    // Allowed visual forms
    allowed: [
      'flowingWaves',
      'halos',
      'breathingGradients',
      'softArcs',
      'ambientFields',
    ],

    // Disallowed (NEVER use these)
    disallowed: [
      'barGraphs',
      'meters',
      'percentIndicators', // when always-on
      'gridLines',
      'hardEdges',
    ],

    // Wave visualization defaults
    wave: {
      strokeWidth: 2,
      smoothing: 0.4,        // Bezier curve smoothing
      glowBlur: '8px',
      glowOpacity: 0.3,
    },

    // Halo/glow visualization defaults
    halo: {
      blur: '24px',
      opacity: 0.25,
      pulseDuration: '3s',   // Slow, breathing
    },

    // Gradient visualization defaults
    gradient: {
      noiseIntensity: 0.03,  // Subtle grain
      transitionDuration: '2s',
      depth: 'radial',       // Radial or diagonal, never flat
    },
  },

  /**
   * Z-Index Scale
   */
  zIndex: {
    base: 0,
    dropdown: 1000,
    sticky: 1020,
    fixed: 1030,
    modalBackdrop: 1040,
    modal: 1050,
    popover: 1060,
    tooltip: 1070,
    toast: 1300,
  },

  /**
   * Breakpoint System (responsive design)
   * Based on common device widths
   */
  breakpoints: {
    xs: '0px',       // Mobile (portrait)
    sm: '600px',     // Mobile (landscape) / Small tablet
    md: '900px',     // Tablet
    lg: '1200px',    // Desktop
    xl: '1536px',    // Large desktop / Wide screens
  },

  /**
   * Component-Specific Tokens
   * Predefined sizes and styles for major UI components
   */
  /**
   * Component-Specific Tokens (Design Language §4)
   * Surfaces, not cards. Hierarchy by space and subtle glass borders.
   * Sidebar is muscle memory UI (low contrast, no visual drama).
   */
  components: {
    playerBar: {
      height: '96px',
      zIndex: 1030,
      background: 'rgba(11, 16, 32, 0.85)',        // Deep blue-black (translucent)
      backdropFilter: 'blur(24px) saturate(1.2)',
      borderTop: 'none',                           // Top edge blends with content
      shadow: '0 -8px 32px rgba(0, 0, 0, 0.28)',   // Depth via shadow
    },

    sidebar: {
      width: '256px',
      collapsedWidth: '72px',
      background: 'rgba(16, 23, 41, 0.20)',        // Ultra-low contrast for starfield visibility (muscle memory UI - §4.3)
      backdropFilter: 'blur(6px) saturate(0.95)',  // Softer blur to preserve starfield
      borderRight: '1px solid rgba(255, 255, 255, 0.05)', // Very subtle glass border for light-catching
      shadow: '2px 0 8px rgba(0, 0, 0, 0.08)',     // Lighter shadow
    },

    rightPanel: {
      width: '360px',
      minWidth: '300px',
      background: 'rgba(16, 23, 41, 0.50)',        // Semi-transparent for starfield visibility
      backdropFilter: 'blur(10px) saturate(1.05)', // Softer blur to preserve starfield
      borderLeft: 'none',                          // Left edge blends with main content
      shadow: '-2px 0 12px rgba(0, 0, 0, 0.10)',   // Subtle shadow for depth
    },

    albumCard: {
      size: '200px',               // Increased from 160px
      borderRadius: '12px',        // lg (12px minimum for cards)
      hoverScale: 1.04,            // Increased from 1.05 for subtlety
      hoverShadow: '0 8px 24px rgba(0, 0, 0, 0.24)',
    },

    albumCover: {
      borderRadius: '16px',        // xl (large panels)
      shadow: '0 12px 32px rgba(0, 0, 0, 0.28)',
      hoverShadow: '0 16px 40px rgba(0, 0, 0, 0.32)',
    },

    button: {
      primary: {
        padding: '12px 24px',
        borderRadius: '8px',
        fontSize: '14px',
        fontWeight: 500,
      },
      icon: {
        size: '56px',
        borderRadius: '9999px',  // full circle
      },
    },

    searchBar: {
      height: '48px',
      borderRadius: '24px',  // Pill shape
      background: 'rgba(31, 41, 54, 0.60)',
      padding: '0 16px',
    },
  },

  /**
   * Gradient System (Soft Violet + Electric Aqua + subtle dark + glass overlays)
   */
  gradients: {
    // Brand gradients (solid)
    aurora: 'linear-gradient(135deg, #7366F0 0%, #5A5CC4 100%)',              // Aurora (Soft Violet → darker)
    auroraSoft: 'linear-gradient(135deg, rgba(115, 102, 240, 0.80) 0%, rgba(90, 92, 196, 0.80) 100%)', // Aurora soft (overlays)
    auroraVertical: 'linear-gradient(180deg, #7366F0 0%, #5A5CC4 100%)',      // Aurora vertical (headers)
    aqua: 'linear-gradient(135deg, #47D6FF 0%, #00BCC4 100%)',                // Aqua (audio-reactive)
    darkSubtle: 'linear-gradient(180deg, #1B232E 0%, #131A24 100%)',          // Dark subtle (background transitions)

    // Glass gradients (translucent overlays)
    glassViolet: 'linear-gradient(135deg, rgba(115, 102, 240, 0.08) 0%, rgba(90, 92, 196, 0.12) 100%)',   // Glass violet tint
    glassAqua: 'linear-gradient(135deg, rgba(71, 214, 255, 0.06) 0%, rgba(0, 188, 196, 0.10) 100%)',     // Glass aqua tint
    glassShimmer: 'linear-gradient(135deg, rgba(255, 255, 255, 0.05) 0%, rgba(255, 255, 255, 0.02) 50%, rgba(255, 255, 255, 0.08) 100%)', // Glass shimmer

    // Mesh gradients (multi-color glass)
    glassMesh: 'radial-gradient(at 0% 0%, rgba(115, 102, 240, 0.15) 0%, transparent 50%), radial-gradient(at 100% 100%, rgba(71, 214, 255, 0.12) 0%, transparent 50%)',

    // Border gradients (for glass edges)
    borderGlow: 'linear-gradient(135deg, rgba(115, 102, 240, 0.4) 0%, rgba(71, 214, 255, 0.3) 100%)',
    borderSubtle: 'linear-gradient(135deg, rgba(255, 255, 255, 0.08) 0%, rgba(255, 255, 255, 0.12) 100%)',

    // Decorative gradients (for album art placeholders, mood visualization)
    // Style Guide §1.4: Gradients must feel alive, not graphic-design perfect
    decorative: {
      neonSunset: 'linear-gradient(135deg, #ff6b9d 0%, #ffa502 100%)',
      deepOcean: 'linear-gradient(135deg, #4b7bec 0%, #26de81 100%)',
      electricPurple: 'linear-gradient(135deg, #c44569 0%, #7366F0 100%)',
      cosmicBlue: 'linear-gradient(135deg, #0f2027 0%, #203a43 50%, #2c5364 100%)',
      gradientPink: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
      gradientBlue: 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
      gradientGreen: 'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)',
      gradientSunset: 'linear-gradient(135deg, #fa709a 0%, #fee140 100%)',
      gradientTeal: 'linear-gradient(135deg, #30cfd0 0%, #330867 100%)',
      gradientPastel: 'linear-gradient(135deg, #a8edea 0%, #fed6e3 100%)',
      gradientRose: 'linear-gradient(135deg, #ff9a9e 0%, #fecfef 100%)',
    },

    // Overlay gradients (for fades, scrim effects)
    overlay: {
      bottomFade: 'linear-gradient(to top, rgba(11, 16, 32, 0.8), transparent)',
      topFade: 'linear-gradient(to bottom, rgba(11, 16, 32, 0.8), transparent)',
      radialDark: 'radial-gradient(circle, transparent 0%, rgba(11, 16, 32, 0.6) 100%)',
    },
  },

  /**
   * Glass Surface Presets (Glassmorphism)
   * Ready-to-use glass surface styles for common components
   */
  /**
   * Glass Surface Presets (Design Language §4.1)
   * Continuous surfaces, not boxed cards.
   * Subtle glass borders catch light - depth via borders, spacing, and shadow.
   */
  glass: {
    // Subtle glass (calm overlays - for idle states)
    subtle: {
      background: 'rgba(21, 29, 47, 0.25)',         // Semi-transparent for starfield visibility
      backdropFilter: 'blur(6px) saturate(1.05)',   // Softer blur to preserve starfield
      border: '1px solid rgba(255, 255, 255, 0.15)', // Enhanced border for light-catching
      boxShadow: '0 4px 16px rgba(0, 0, 0, 0.12), 0 0 0 1px rgba(255, 255, 255, 0.08)', // Inner glow
    },

    // Medium glass (panels, surfaces)
    medium: {
      background: 'rgba(21, 29, 47, 0.40)',         // Semi-transparent for starfield visibility
      backdropFilter: 'blur(8px) saturate(1.08)',   // Softer blur to preserve starfield
      border: '1px solid rgba(255, 255, 255, 0.18)', // Enhanced border for light edges
      boxShadow: '0 8px 24px rgba(0, 0, 0, 0.16), 0 0 0 1px rgba(255, 255, 255, 0.12)', // Inner glow
    },

    // Strong glass (modals, prominent surfaces)
    strong: {
      background: 'rgba(21, 29, 47, 0.55)',         // Semi-transparent for starfield visibility
      backdropFilter: 'blur(12px) saturate(1.1)',   // Softer blur to preserve starfield
      border: '1px solid rgba(255, 255, 255, 0.22)', // Enhanced border for light-catching
      boxShadow: '0 16px 48px rgba(0, 0, 0, 0.24), 0 0 0 1px rgba(255, 255, 255, 0.18)', // Deep shadow + inner glow
    },

    // Violet-tinted glass (accent surfaces - playback/active states)
    violet: {
      background: 'linear-gradient(135deg, rgba(115, 102, 240, 0.12) 0%, rgba(21, 29, 47, 0.50) 100%)', // Stronger violet tint
      backdropFilter: 'blur(28px) saturate(1.3)',   // Intensified blur (24→28px) for vibrant accent glass
      border: '1px solid rgba(115, 102, 240, 0.28)', // Enhanced violet border (20→28%) for vivid light-catching
      boxShadow: '0 8px 32px rgba(115, 102, 240, 0.20), 0 0 0 1px rgba(115, 102, 240, 0.22)', // Violet inner glow intensified (15→22%)
    },

    // Aqua-tinted glass (audio-reactive surfaces - processing/energy)
    aqua: {
      background: 'linear-gradient(135deg, rgba(71, 214, 255, 0.10) 0%, rgba(21, 29, 47, 0.50) 100%)', // Stronger aqua tint
      backdropFilter: 'blur(28px) saturate(1.3)',   // Intensified blur (24→28px) for energetic glass
      border: '1px solid rgba(71, 214, 255, 0.25)', // Enhanced aqua border (18→25%) for bright light edges
      boxShadow: '0 8px 32px rgba(71, 214, 255, 0.18), 0 0 0 1px rgba(71, 214, 255, 0.18)', // Aqua inner glow intensified (12→18%)
    },
  },

  /**
   * Animation System
   */
  animations: {
    pulse: {
      keyframes: `
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
      `,
      duration: '2s',
      timing: 'ease-in-out',
      iteration: 'infinite',
    },

    fadeIn: {
      keyframes: `
        @keyframes fadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }
      `,
      duration: '200ms',
      timing: 'ease',
    },

    slideUp: {
      keyframes: `
        @keyframes slideUp {
          from { transform: translateY(10px); opacity: 0; }
          to { transform: translateY(0); opacity: 1; }
        }
      `,
      duration: '300ms',
      timing: 'ease-out',
    },
  },
} as const;

/**
 * Helper function to get color with opacity
 */
export function withOpacity(color: string, opacity: number): string {
  // Simple hex to rgba conversion for 6-digit hex colors
  if (color.startsWith('#') && color.length === 7) {
    const r = parseInt(color.slice(1, 3), 16);
    const g = parseInt(color.slice(3, 5), 16);
    const b = parseInt(color.slice(5, 7), 16);
    return `rgba(${r}, ${g}, ${b}, ${opacity})`;
  }
  return color;
}

/**
 * Type exports for TypeScript autocomplete
 */
export type DesignTokens = typeof tokens;
export type ColorToken = keyof typeof tokens.colors;
export type SpacingToken = keyof typeof tokens.spacing;
export type TypographyToken = keyof typeof tokens.typography;
