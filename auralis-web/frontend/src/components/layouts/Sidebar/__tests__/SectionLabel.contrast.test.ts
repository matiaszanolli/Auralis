/**
 * Sidebar SectionLabel contrast (#4451)
 *
 * SectionLabel ("LIBRARY", etc.) used text.disabled (40% white) at fontSize.xs
 * AND an extra `opacity: 0.4`, compounding to ~16% effective alpha against the
 * dark glass sidebar — well under WCAG AA, and the text is small (needs 4.5:1).
 * It now uses text.metadata (60% white) with no compounded opacity.
 *
 * This computes the real WCAG contrast from the live tokens against the
 * effective (composited) sidebar background so a regression back to a too-faint
 * color is caught. Sibling of the #4182 MediaCardInfo contrast guard.
 */

import { describe, it, expect } from 'vitest';
import { tokens } from '@/design-system';
import { composite, contrastRatio, withOpacity } from '@/test/contrast';

// The sidebar surface is a translucent glass (semantics.ts: sidebar.background)
// over the app base (colors.bg.level0). Composite them to the opaque color the
// text actually sits on.
const SIDEBAR_GLASS = 'rgba(16, 23, 41, 0.20)';
const APP_BASE = tokens.colors.bg.level0; // '#0B1020'
const [r, g, b] = composite(SIDEBAR_GLASS, APP_BASE);
const SIDEBAR_BG = `rgb(${r}, ${g}, ${b})`;

describe('Sidebar SectionLabel contrast (#4451)', () => {
  it('text.metadata meets WCAG AA (>= 4.5:1) on the sidebar surface', () => {
    expect(contrastRatio(tokens.colors.text.metadata, SIDEBAR_BG)).toBeGreaterThanOrEqual(4.5);
  });

  it('the previous text.disabled compounded with opacity 0.4 would have failed AA (discriminating guard)', () => {
    const previousEffective = withOpacity(tokens.colors.text.disabled, 0.4);
    expect(contrastRatio(previousEffective, SIDEBAR_BG)).toBeLessThan(4.5);
  });
});
