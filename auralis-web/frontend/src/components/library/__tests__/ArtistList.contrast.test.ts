/**
 * Artist list text contrast, both theme modes (#4534)
 *
 * ArtistName and ArtistInfo read tokens.colors.text.primary / .tertiary —
 * dark-only primitives with no light variant, fixed at rgba(255,255,255,0.95)
 * and 60% white. The artist cards they sit in used tokens.glass.starfield.faint,
 * likewise a fixed dark tint. In light mode that put near-white text on a card
 * composited over the #F8F9FD canvas: about 1.05:1, against a 4.5:1 AA floor
 * and below even the 3:1 large-text floor.
 *
 * The Artists tab is an always-visible primary browsing surface, so this is
 * pinned at both modes rather than at the dark surface alone.
 */

import { describe, it, expect } from 'vitest';
import { tokens } from '@/design-system';
import { contrastRatio, composite, withOpacity } from '@/test/contrast';
import { getSemanticTheme, type ThemeMode } from '@/theme/semanticTheme';

const MODES: ThemeMode[] = ['dark', 'light'];

const rgb = ([r, g, b]: [number, number, number]) =>
  `rgb(${Math.round(r)}, ${Math.round(g)}, ${Math.round(b)})`;

/** StyledListItemButton's translucent card, composited over the app canvas. */
function cardSurface(mode: ThemeMode): string {
  const theme = getSemanticTheme(mode);
  return rgb(composite(theme.surfaceTranslucent, theme.canvas));
}

/** The hover surface, where ArtistName also switches to the accent colour. */
function hoverSurface(mode: ThemeMode): string {
  const theme = getSemanticTheme(mode);
  return rgb(composite(theme.surfaceRaised, theme.canvas));
}

describe.each(MODES)('Artist list contrast — %s mode (#4534)', (mode) => {
  const theme = getSemanticTheme(mode);

  it('ArtistName (textPrimary) meets AA on the card', () => {
    expect(contrastRatio(theme.textPrimary, cardSurface(mode))).toBeGreaterThanOrEqual(4.5);
  });

  it('ArtistInfo (textMuted) meets AA on the card', () => {
    expect(contrastRatio(theme.textMuted, cardSurface(mode))).toBeGreaterThanOrEqual(4.5);
  });

  it('AlphabetDivider meets AA on the canvas', () => {
    expect(contrastRatio(theme.textMuted, theme.canvas)).toBeGreaterThanOrEqual(4.5);
  });

  it('re-adding the divider opacity multiplier would drop it below AA', () => {
    // The removed `opacity: 0.7` measured 4.08:1 dark / 3.04:1 light on this
    // 10px uppercase label. Pinned so it cannot quietly come back.
    expect(
      contrastRatio(withOpacity(theme.textMuted, 0.7), theme.canvas),
    ).toBeLessThan(4.5);
  });

  it('ArtistName on hover (accent) meets the 3:1 non-text floor', () => {
    expect(
      contrastRatio(tokens.colors.accent.primary, hoverSurface(mode)),
    ).toBeGreaterThanOrEqual(3);
  });
});

describe('Artist list contrast — discriminating guards', () => {
  it('the reported light-mode failure would still be caught', () => {
    // The exact pairing from the issue: raw dark-only text.primary on the
    // light artist card, measured at ~1.05:1.
    const ratio = contrastRatio(tokens.colors.text.primary, cardSurface('light'));
    expect(ratio).toBeLessThan(4.5);
    expect(ratio).toBeLessThan(3);
  });

  it('the two modes resolve to genuinely different surfaces', () => {
    expect(cardSurface('light')).not.toBe(cardSurface('dark'));
  });
});
