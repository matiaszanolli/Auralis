/**
 * Helper functions for deriving colour values from hex tokens.
 * Extracted from the former tokens.ts monolith (#4079).
 */

/** RGB channels of a colour, 0-255. */
export interface RgbChannels {
  r: number;
  g: number;
  b: number;
}

/**
 * Parse a 6-digit hex colour into its RGB channels.
 *
 * Returns `null` for anything that isn't `#RRGGBB` (named colours, `rgba()`
 * strings, CSS variables) so callers can fall through to the original value
 * rather than emitting `rgba(NaN, NaN, NaN, …)`. The single implementation of
 * this parse — four call sites had their own copies (#4464), and
 * colorExtraction's brand fallback hand-wrote the channel numbers (#4463).
 */
export function hexToRgb(color: string): RgbChannels | null {
  if (!color.startsWith('#') || color.length !== 7) {
    return null;
  }
  const r = parseInt(color.slice(1, 3), 16);
  const g = parseInt(color.slice(3, 5), 16);
  const b = parseInt(color.slice(5, 7), 16);
  if (Number.isNaN(r) || Number.isNaN(g) || Number.isNaN(b)) {
    return null;
  }
  return { r, g, b };
}

/**
 * Helper function to get color with opacity.
 *
 * Non-hex input is returned unchanged, so a theme-aware CSS variable passed
 * here degrades to a fully opaque colour instead of an invalid one.
 */
export function withOpacity(color: string, opacity: number): string {
  const rgb = hexToRgb(color);
  if (!rgb) {
    return color;
  }
  return `rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, ${opacity})`;
}
