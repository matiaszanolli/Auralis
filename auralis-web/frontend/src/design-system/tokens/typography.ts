/**
 * Auralis Design System Tokens — see ./README or tokens barrel.
 * Split from the former monolithic tokens.ts (#4079). Do not add cross-category
 * references here; each category is self-contained and merged in the barrel.
 */


  /**
   * Typography System (Design Language §3)
   * Asap (Google Fonts) - clean, modern sans-serif for all UI text
   * Typography should disappear when listening.
   */
export const typography = {
    fontFamily: {
      primary: 'Asap, "Segoe UI", sans-serif',                                     // Primary UI font for all text
      header: 'Asap, Arial, sans-serif',                                           // Headers, titles (same family, heavier weights)
      mono: "'JetBrains Mono', 'Courier New', monospace",                          // Technical readouts (dB, Hz, LUFS)
      system: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif',
    },

    fontSize: {
      xs: '11px',      // Micro labels, timestamps (WCAG AA floor for body text)
      sm: '13px',      // Small text, metadata, captions
      base: '14px',    // Standard body text
      md: '16px',      // Larger body, input labels
      lg: '18px',      // Track titles, card headers
      xl: '22px',      // Album titles, section headers
      '2xl': '28px',   // Page headers, artist names
      '3xl': '36px',   // Large headers, hero text
      '4xl': '56px',   // Display, hero text
      '5xl': '72px',   // Ultra-large display
      // #3639: named display sizes for prominent typography that doesn't fit
      // the body-text scale (artwork glyphs, empty-state icons, hero numbers).
      // Kept distinct from xs-5xl so the body scale stays linear.
      display: '48px',  // Track-info artwork glyph
      hero: '60px',     // Hero-size display
      huge: '80px',     // Empty-state placeholder glyphs
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
} as const;
