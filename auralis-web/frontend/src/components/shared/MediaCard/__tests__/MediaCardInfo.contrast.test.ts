/**
 * MediaCardInfo caption contrast, both theme modes (#4182, #4534)
 *
 * #4182 fixed the dark-mode axis: the caption used text.disabled (40% white) at
 * 11px on the card surface, ~3.68:1, below the AA 4.5:1 floor for small text.
 *
 * #4534 is the light-mode axis of the same defect, and this test could not see
 * it because CARD_BG was hardcoded to the dark surface '#1A2338'. The component
 * read tokens.colors.text.* and the card read tokens.glass.subtle.background —
 * all dark-only primitives with no light variant — so in light mode near-white
 * text rendered on a card that composited to roughly #BFC2CA over the light
 * canvas: about 1.74:1. A test pinned to a single surface cannot detect a
 * whole-mode failure, so both the surface and the text now resolve from the
 * semantic theme, per mode.
 */

import { describe, it, expect } from 'vitest';
import { tokens } from '@/design-system';
import { contrastRatio, composite } from '@/test/contrast';
import { getSemanticTheme, type ThemeMode } from '@/theme/semanticTheme';

const MODES: ThemeMode[] = ['dark', 'light'];

const rgb = ([r, g, b]: [number, number, number]) =>
  `rgb(${Math.round(r)}, ${Math.round(g)}, ${Math.round(b)})`;

/**
 * The card's actually-painted surface. surfaceTranslucent is translucent, so it
 * must be composited over the canvas beneath it to get the colour the text is
 * really read against — the same compositing that produced the 1.74:1 failure.
 */
function cardSurface(mode: ThemeMode): string {
  const theme = getSemanticTheme(mode);
  return rgb(composite(theme.surfaceTranslucent, theme.canvas));
}

describe.each(MODES)('MediaCardInfo contrast — %s mode (#4534)', (mode) => {
  const theme = getSemanticTheme(mode);
  const surface = cardSurface(mode);

  it('title (textPrimary) meets AA', () => {
    expect(contrastRatio(theme.textPrimary, surface)).toBeGreaterThanOrEqual(4.5);
  });

  it('artist line (textSecondary) meets AA', () => {
    expect(contrastRatio(theme.textSecondary, surface)).toBeGreaterThanOrEqual(4.5);
  });

  it('metadata caption (textMuted) meets AA', () => {
    expect(contrastRatio(theme.textMuted, surface)).toBeGreaterThanOrEqual(4.5);
  });

  it('the playing-state accent title meets the 3:1 non-text floor', () => {
    // The title switches to the brand accent while playing. The accent is
    // deliberately shared across modes, so it is held to 3:1 rather than 4.5:1.
    expect(contrastRatio(tokens.colors.accent.primary, surface)).toBeGreaterThanOrEqual(3);
  });
});

describe('MediaCardInfo contrast — discriminating guards', () => {
  it('the pre-#4182 text.disabled would still fail AA in dark mode', () => {
    expect(contrastRatio(tokens.colors.text.disabled, cardSurface('dark'))).toBeLessThan(4.5);
  });

  it('the pre-#4534 dark-only text on the light card would have failed AA', () => {
    // Exactly the reported regression: raw tokens.colors.text.primary
    // (near-white, no light variant) on the light-mode card. If this ever
    // passes, the light palette has drifted dark and the assertions above have
    // stopped discriminating.
    expect(contrastRatio(tokens.colors.text.primary, cardSurface('light'))).toBeLessThan(4.5);
  });

  it('the two modes resolve to genuinely different surfaces', () => {
    // Guards against a future where light and dark collapse to one palette and
    // every per-mode assertion above passes for the wrong reason.
    expect(cardSurface('light')).not.toBe(cardSurface('dark'));
  });
});
