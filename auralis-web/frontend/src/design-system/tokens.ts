/**
 * Auralis Design System Tokens
 *
 * Single source of truth for all design values.
 * ALL components MUST use these tokens - no hardcoded values allowed.
 *
 * @see docs/guides/UI_DESIGN_GUIDELINES.md
 */

export const tokens = {
  /**
   * Color System - Auralis Design Language v1.2.0
   * Deep blue-black base (#0B1020 range) with soft violet/indigo primary,
   * teal/cyan for audio state, warm amber for energy/highlights.
   * Dark mode is canonical. Surfaces, not cards.
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

    // Semantic accent colors
    semantic: {
      success: '#10B981',      // Success (positive)
      warning: '#F59E0B',      // Warning (caution)
      error: '#EF4444',        // Error (critical)
      info: '#3B82F6',         // Info (informational)
    },

    // Text colors
    text: {
      primary: '#FFFFFF',      // Ultra White - titles, emphasis
      secondary: '#C1C8EF',    // Lavender Smoke - secondary text, labels
      tertiary: '#8B92B0',     // Muted purple-gray - tertiary text
      muted: '#6B7194',        // Muted - disabled, hint text
      disabled: '#4A5073',     // Disabled text (very muted)
      inverse: '#0D111A',      // For light backgrounds
    },

    // Border colors (using soft opacity + brand colors)
    border: {
      light: 'rgba(115, 102, 240, 0.12)',   // Subtle borders (soft violet)
      medium: 'rgba(115, 102, 240, 0.24)',  // Standard borders
      heavy: 'rgba(115, 102, 240, 0.40)',   // Emphasized borders
      accent: '#7366F0',                     // Accent borders (soft violet)
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
   * Motion Language (Design Language §5)
   * - Hover: 120–150ms
   * - State changes: 300–600ms
   * - Motion is slow, heavy, analog (never fast oscillation)
   * - Motion should feel inevitable, not reactive
   */
  transitions: {
    // Durations (Design Language §5.2)
    fast: '150ms',     // Hover states (120–150ms)
    base: '400ms',     // State changes (300–600ms)
    slow: '500ms',     // State changes (300–600ms)
    verySlow: '600ms', // Audio-reactive visuals (lag audio by ~100ms)

    // Easing functions (slow, heavy, analog)
    easeOut: 'cubic-bezier(0.25, 0.46, 0.45, 0.94)',    // Audio-like fluidity
    easeInOut: 'cubic-bezier(0.4, 0, 0.6, 1)',          // Natural
    easeSmooth: 'cubic-bezier(0.25, 0.1, 0.25, 1)',     // Slow, heavy (Design Language §5.1)

    // Combined (duration + easing) - Motion feels inevitable
    fast_out: '150ms cubic-bezier(0.25, 0.46, 0.45, 0.94)',
    base_inOut: '400ms cubic-bezier(0.4, 0, 0.6, 1)',
    slow_inOut: '500ms cubic-bezier(0.4, 0, 0.6, 1)',
    verySlow_inOut: '600ms cubic-bezier(0.25, 0.1, 0.25, 1)',

    // Property-specific (slower, analog)
    color: '400ms color cubic-bezier(0.4, 0, 0.6, 1)',
    background: '400ms background-color cubic-bezier(0.4, 0, 0.6, 1)',
    transform: '500ms transform cubic-bezier(0.25, 0.1, 0.25, 1)',
    opacity: '400ms opacity cubic-bezier(0.4, 0, 0.6, 1)',
    all: '400ms all cubic-bezier(0.4, 0, 0.6, 1)',
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
      background: 'rgba(16, 23, 41, 0.25)',        // Ultra-low contrast (muscle memory UI - §4.3, R3 refinement)
      backdropFilter: 'blur(12px) saturate(0.9)',  // Slightly increased blur for subtle glass effect
      borderRight: '1px solid rgba(255, 255, 255, 0.05)', // Very subtle glass border for light-catching
      shadow: '2px 0 8px rgba(0, 0, 0, 0.08)',     // Lighter shadow
    },

    rightPanel: {
      width: '360px',
      minWidth: '300px',
      background: 'rgba(16, 23, 41, 0.60)',        // Slightly lifted from sidebar
      backdropFilter: 'blur(16px) saturate(1.1)',
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
      background: 'rgba(21, 29, 47, 0.30)',         // Increased opacity for more presence
      backdropFilter: 'blur(24px) saturate(1.1)',   // Intensified blur (20→24px) for more dramatic glass effect
      border: '1px solid rgba(255, 255, 255, 0.15)', // Enhanced border (10→15%) for better light-catching
      boxShadow: '0 4px 16px rgba(0, 0, 0, 0.12), 0 0 0 1px rgba(255, 255, 255, 0.08)', // Inner glow intensified (5→8%)
    },

    // Medium glass (panels, surfaces)
    medium: {
      background: 'rgba(21, 29, 47, 0.45)',         // Increased opacity
      backdropFilter: 'blur(32px) saturate(1.15)',  // Intensified blur (28→32px) for stronger glass
      border: '1px solid rgba(255, 255, 255, 0.18)', // Enhanced border (12→18%) for prominent light edges
      boxShadow: '0 8px 24px rgba(0, 0, 0, 0.16), 0 0 0 1px rgba(255, 255, 255, 0.12)', // Inner glow intensified (8→12%)
    },

    // Strong glass (modals, prominent surfaces)
    strong: {
      background: 'rgba(21, 29, 47, 0.65)',         // Increased opacity for solid presence
      backdropFilter: 'blur(40px) saturate(1.2)',   // Maximum blur (32→40px) for most dramatic glass
      border: '1px solid rgba(255, 255, 255, 0.22)', // Enhanced border (15→22%) for maximum light-catching
      boxShadow: '0 16px 48px rgba(0, 0, 0, 0.24), 0 0 0 1px rgba(255, 255, 255, 0.18)', // Inner glow intensified (12→18%)
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
