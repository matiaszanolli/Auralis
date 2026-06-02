/**
 * Auralis Design System Tokens — see ./README or tokens barrel.
 * Split from the former monolithic tokens.ts (#4079). Do not add cross-category
 * references here; each category is self-contained and merged in the barrel.
 */


  /**
   * Spacing System - Organic Rhythm (Design Language §4.2)
   * Variable spacing creates natural grouping and breathing room.
   * Tight within groups, generous between sections.
   */
export const spacing = {
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
} as const;

  /**
   * Border Radius System - Organic Curves (Design Language §4.4)
   * Softer, more generous curves create fluid, organic aesthetic.
   * Minimum 8px for any interactive element.
   */
export const borderRadius = {
    none: '0',
    sm: '8px',       // Minimum for any rounded element (increased from 4px)
    md: '12px',      // Standard cards, buttons (increased from 8px)
    lg: '16px',      // Large cards, panels (increased from 12px)
    xl: '20px',      // Hero cards, modals (increased from 16px)
    '2xl': '24px',   // Maximum curve for rectangles (new)
    '3xl': '32px',   // Ultra-round for special elements (new)
    full: '9999px',  // Pill shape, circular buttons
} as const;

  /**
   * Backdrop Blur System (Glassmorphism)
   * Premium translucent surfaces with background blur
   */
export const blur = {
    none: 'none',
    xs: 'blur(4px)',
    sm: 'blur(8px)',
    md: 'blur(12px)',
    lg: 'blur(16px)',
    xl: 'blur(24px)',
    xxl: 'blur(32px)',
} as const;

  /**
   * Opacity System (UX Polish - Phase 4b)
   * Standardized opacity levels for fading UI elements
   *
   * Based on fade patterns established in Phases 1-4a:
   * - Infrastructure elements (labels, dividers) fade more (~40-60%)
   * - Inactive content (icons, text) fade less (~15-30%)
   * - Duration badges and secondary UI fade moderately (~20-40%)
   */
export const opacity = {
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
} as const;

  /**
   * Z-Index Scale
   */
export const zIndex = {
    base: 0,
    content: 1,
    elevated: 10,
    dropdown: 1000,
    sticky: 1020,
    fixed: 1030,
    modalBackdrop: 1040,
    modal: 1050,
    popover: 1060,
    tooltip: 1070,
    toast: 1300,
    debug: 10000,
} as const;

  /**
   * Breakpoint System (responsive design)
   * Based on common device widths
   */
export const breakpoints = {
    xs: '0px',       // Mobile (portrait)
    sm: '600px',     // Mobile (landscape) / Small tablet
    md: '900px',     // Tablet
    lg: '1200px',    // Desktop
    xl: '1536px',    // Large desktop / Wide screens
} as const;
