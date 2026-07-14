/**
 * Auralis Design System Tokens — see ./README or tokens barrel.
 * Split from the former monolithic tokens.ts (#4079). Do not add cross-category
 * references here; each category is self-contained and merged in the barrel.
 */


  /**
   * Shadow System (Ambient opacity - no harsh black)
   * Elevation levels + audio-reactive glows + glassmorphism depth
   */
export const shadows = {
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

    // Compact keyframe glows (10/20px blur) — single source for the global
    // --glow-* CSS vars consumed by glow/pulse animations (#4201).
    glowAccentMedium: '0 0 10px rgba(115, 102, 240, 0.5)',
    glowAccentStrong: '0 0 20px rgba(115, 102, 240, 0.8)',
    glowAquaMedium: '0 0 10px rgba(71, 214, 255, 0.5)',
    glowAquaStrong: '0 0 20px rgba(71, 214, 255, 0.8)',

    // Glass depth shadows (for glassmorphism layering)
    glassSubtle: '0 4px 16px rgba(0, 0, 0, 0.12), 0 0 0 1px rgba(255, 255, 255, 0.05)', // Glass surface
    glassMd: '0 8px 32px rgba(0, 0, 0, 0.18), 0 0 0 1px rgba(255, 255, 255, 0.08)',     // Elevated glass
    glassStrong: '0 16px 48px rgba(0, 0, 0, 0.24), 0 0 0 1px rgba(255, 255, 255, 0.12)', // Prominent glass
} as const;

  /**
   * Elevation System (UX Polish - Phase 4b)
   * Standardized depth patterns for consistent visual hierarchy
   *
   * Based on shadow-based depth (no hard borders) established in Phases 1-4a:
   * - Cards use resting + hover elevations
   * - Panels use separation shadows (left/right)
   * - Sections use subtle background differences + spacing
   */
export const elevation = {
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
    verySlow: '600ms',

    // Easing functions (slow, heavy, analog - NO BOUNCE)
    easeOut: 'cubic-bezier(0.25, 0.46, 0.45, 0.94)',    // Fluid deceleration
    easeInOut: 'cubic-bezier(0.4, 0, 0.6, 1)',          // Natural, weighted
    easeSmooth: 'cubic-bezier(0.25, 0.1, 0.25, 1)',     // Slow, heavy, analog

    // Combined (duration + easing) - Motion feels inevitable
    hover_out: '150ms cubic-bezier(0.25, 0.46, 0.45, 0.94)',
    state_inOut: '450ms cubic-bezier(0.4, 0, 0.6, 1)',
    slow_inOut: '600ms cubic-bezier(0.4, 0, 0.6, 1)',

    // Semantic combined aliases — actively used (e.g. ThemeToggle, ContextMenu,
    // EmptyState). Internal convenience names, not backwards-compat shims (#4402).
    fast_out: '150ms cubic-bezier(0.25, 0.46, 0.45, 0.94)',
    base_inOut: '450ms cubic-bezier(0.4, 0, 0.6, 1)',
    verySlow_inOut: '600ms cubic-bezier(0.25, 0.1, 0.25, 1)',

    // Property-specific
    color: '450ms color cubic-bezier(0.4, 0, 0.6, 1)',
    background: '450ms background-color cubic-bezier(0.4, 0, 0.6, 1)',
    transform: '600ms transform cubic-bezier(0.25, 0.1, 0.25, 1)',
    opacity: '450ms opacity cubic-bezier(0.4, 0, 0.6, 1)',
    all: '450ms all cubic-bezier(0.4, 0, 0.6, 1)',
} as const;

  /**
   * Audio-Reactive Motion (Style Guide §6.3)
   * Rules:
   * - Heavy smoothing
   * - No frame-perfect sync
   * - Motion represents trend, not sample data
   * - UI should feel like it's interpreting, not measuring
   */
export const audioReactive = {
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
} as const;

  /**
   * Animation System
   */
export const animations = {
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
} as const;
