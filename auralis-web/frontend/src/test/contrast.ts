/**
 * WCAG contrast helpers for accessibility tests.
 *
 * Computes the real WCAG 2.x contrast ratio between a (possibly translucent)
 * foreground color and a background, so token/color regressions that drop text
 * below the AA minimum are caught. Extracted from the #4182 MediaCardInfo
 * contrast test so multiple a11y tests share one implementation (#4451).
 */

type RGBA = [number, number, number, number];

/** Parse a #hex or rgb()/rgba() string into [r, g, b, a] (a in 0..1). */
export function parseColor(c: string): RGBA {
  if (c.startsWith('#')) {
    const h = c.slice(1);
    return [
      parseInt(h.slice(0, 2), 16),
      parseInt(h.slice(2, 4), 16),
      parseInt(h.slice(4, 6), 16),
      1,
    ];
  }
  const m = c.match(/rgba?\(([^)]+)\)/);
  if (!m) throw new Error(`Unparseable color: ${c}`);
  const p = m[1].split(',').map((s) => parseFloat(s.trim()));
  return [p[0], p[1], p[2], p[3] ?? 1];
}

/** Alpha-composite a (possibly translucent) foreground over another color. */
export function composite(fg: string, bg: string): [number, number, number] {
  const [fr, fgc, fb, fa] = parseColor(fg);
  const [br, bgc, bb] = compositeToOpaque(bg);
  return [
    fr * fa + br * (1 - fa),
    fgc * fa + bgc * (1 - fa),
    fb * fa + bb * (1 - fa),
  ];
}

/**
 * Resolve a color to an opaque [r, g, b]. If it is already opaque this is a
 * no-op; a translucent color is composited over opaque black as a floor (only
 * used for the background reference, which callers should pass opaque anyway).
 */
function compositeToOpaque(c: string): [number, number, number] {
  const [r, g, b, a] = parseColor(c);
  return [r * a, g * a, b * a];
}

export function relativeLuminance([r, g, b]: [number, number, number]): number {
  const lin = (v: number) => {
    const s = v / 255;
    return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
  };
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}

/**
 * WCAG contrast ratio between `fg` (composited over `bg`) and `bg`.
 * `bg` should be an opaque color.
 */
export function contrastRatio(fg: string, bg: string): number {
  const l1 = relativeLuminance(composite(fg, bg));
  const l2 = relativeLuminance(compositeToOpaque(bg));
  const [hi, lo] = l1 > l2 ? [l1, l2] : [l2, l1];
  return (hi + 0.05) / (lo + 0.05);
}

/**
 * Multiply an rgba/hex color's alpha by an extra factor — models the CSS
 * `opacity` property compounding on top of an already-translucent color token.
 */
export function withOpacity(color: string, opacity: number): string {
  const [r, g, b, a] = parseColor(color);
  return `rgba(${r}, ${g}, ${b}, ${a * opacity})`;
}
