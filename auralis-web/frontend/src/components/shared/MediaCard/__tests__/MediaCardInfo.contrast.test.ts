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
import { contrastRatio } from '@/test/contrast';

// Card surface (colors.bg level3 / elevated).
const CARD_BG = '#1A2338';

describe('MediaCardInfo caption contrast (#4182)', () => {
  it('text.metadata meets WCAG AA (>= 4.5:1) on the card surface', () => {
    expect(contrastRatio(tokens.colors.text.metadata, CARD_BG)).toBeGreaterThanOrEqual(4.5);
  });

  it('the previous text.disabled would have failed AA (discriminating guard)', () => {
    expect(contrastRatio(tokens.colors.text.disabled, CARD_BG)).toBeLessThan(4.5);
  });
});
