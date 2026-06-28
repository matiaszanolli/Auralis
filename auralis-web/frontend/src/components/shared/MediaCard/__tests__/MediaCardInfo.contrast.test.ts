/**
 * MediaCardInfo caption contrast (#4182)
 *
 * The caption used text.disabled (40% white) at 11px on the card surface
 * (#1A2338) — ~3.68:1, below the WCAG AA 4.5:1 minimum for small text. It now
 * uses text.metadata (60% white). This computes the real WCAG contrast ratio
 * from the live tokens so a regression back to a too-faint color is caught.
 */

import { describe, it, expect } from 'vitest';
import { tokens } from '@/design-system';

// Card surface (colors.bg level3 / elevated).
const CARD_BG = '#1A2338';

type RGBA = [number, number, number, number];

function parseColor(c: string): RGBA {
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

/** Alpha-composite a (possibly translucent) foreground over an opaque bg. */
function composite(fg: string, bg: string): [number, number, number] {
  const [fr, fgc, fb, fa] = parseColor(fg);
  const [br, bgc, bb] = parseColor(bg);
  return [
    fr * fa + br * (1 - fa),
    fgc * fa + bgc * (1 - fa),
    fb * fa + bb * (1 - fa),
  ];
}

function relativeLuminance([r, g, b]: [number, number, number]): number {
  const lin = (v: number) => {
    const s = v / 255;
    return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
  };
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}

function contrastRatio(fg: string, bg: string): number {
  const l1 = relativeLuminance(composite(fg, bg));
  const [br, bgc, bb] = parseColor(bg);
  const l2 = relativeLuminance([br, bgc, bb]);
  const [hi, lo] = l1 > l2 ? [l1, l2] : [l2, l1];
  return (hi + 0.05) / (lo + 0.05);
}

describe('MediaCardInfo caption contrast (#4182)', () => {
  it('text.metadata meets WCAG AA (>= 4.5:1) on the card surface', () => {
    expect(contrastRatio(tokens.colors.text.metadata, CARD_BG)).toBeGreaterThanOrEqual(4.5);
  });

  it('the previous text.disabled would have failed AA (discriminating guard)', () => {
    expect(contrastRatio(tokens.colors.text.disabled, CARD_BG)).toBeLessThan(4.5);
  });
});
