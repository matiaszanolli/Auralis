/**
 * Normal-size text must not use text.disabled (#4635)
 *
 * `tokens.colors.text.disabled` is `rgba(255,255,255,0.40)`, calibrated per its
 * own comment only for the WCAG AA **3:1 large-text** floor (>=18px regular /
 * >=14px bold). Against the app's dark surfaces it measures ~3.6-3.8:1, failing
 * the 4.5:1 normal-text requirement — yet it labelled small text in several
 * places, two of them additionally multiplied by a CSS `opacity` on the same
 * element, pushing effective contrast to ~1.9-2.2:1.
 *
 * This is the fourth instance of the same defect (#4182 MediaCardInfo, #4451
 * sidebar labels, then this sweep), so the guard is a shared spec over every
 * fixed site rather than another one-off file.
 *
 * Scope note: genuinely-disabled controls are deliberately excluded. WCAG 2.1
 * SC 1.4.3 exempts "text that is part of an inactive user interface component",
 * and fading a disabled control is the information the style conveys. Those
 * sites keep `text.disabled`; see the classification test at the bottom.
 */

import { describe, it, expect } from 'vitest';
import { tokens } from '@/design-system';
import { composite, contrastRatio, withOpacity } from '@/test/contrast';

const AA_NORMAL = 4.5;

/**
 * The surfaces the fixed text actually sits on. Menus and cards are translucent
 * glass over the app base, so composite down to the opaque colour rather than
 * measuring against the glass value (which would flatter the result).
 */
const APP_BASE = tokens.colors.bg.level0;

function opaque(glass: string, base: string = APP_BASE): string {
  const [r, g, b] = composite(glass, base);
  return `rgb(${r}, ${g}, ${b})`;
}

/** The four dark surfaces normal text is placed on across the fixed sites. */
const SURFACES: Record<string, string> = {
  'bg.level1': tokens.colors.bg.level1,
  'bg.level2': tokens.colors.bg.level2,
  'bg.level3': tokens.colors.bg.level3,
  'bg.level4': tokens.colors.bg.level4,
  // Menu/card glass composited over the app base.
  'glass over base': opaque('rgba(16, 23, 41, 0.20)'),
};

describe('text.metadata clears AA on every surface the fixed sites use (#4635)', () => {
  it.each(Object.entries(SURFACES))(
    'metadata >= 4.5:1 on %s',
    (_name, bg) => {
      expect(contrastRatio(tokens.colors.text.metadata, bg)).toBeGreaterThanOrEqual(AA_NORMAL);
    }
  );
});

describe('the token that was replaced would still fail (discriminating guard)', () => {
  // Without this, the suite above could pass simply because both tokens are
  // legible, proving nothing about the swap.
  it.each(Object.entries(SURFACES))(
    'disabled < 4.5:1 on %s, which is why these sites moved',
    (_name, bg) => {
      expect(contrastRatio(tokens.colors.text.disabled, bg)).toBeLessThan(AA_NORMAL);
    }
  );

  it('disabled still clears the 3:1 large-text floor it IS calibrated for', () => {
    // Pins that the token itself is not broken — only its use on small text was.
    expect(contrastRatio(tokens.colors.text.disabled, tokens.colors.bg.level1))
      .toBeGreaterThanOrEqual(3.0);
  });
});

describe('compounded opacity is gone from the two double-faded sites (#4635)', () => {
  it('TrackDuration: 40% x 50% would have been ~2:1', () => {
    const before = withOpacity(tokens.colors.text.disabled, 0.5);
    expect(contrastRatio(before, tokens.colors.bg.level1)).toBeLessThan(2.5);
  });

  it('TrackDuration now clears AA with no opacity multiplier', () => {
    expect(contrastRatio(tokens.colors.text.metadata, tokens.colors.bg.level1))
      .toBeGreaterThanOrEqual(AA_NORMAL);
  });

  it('a disabled menu item stays visibly present rather than near-invisible', () => {
    // Exempt from 4.5:1 as an inactive control, but 40% x 50% ~= 1.9:1 reads as
    // "absent", not "disabled". With the multiplier removed it is legible enough
    // to be perceived as a disabled entry.
    const compounded = withOpacity(tokens.colors.text.disabled, 0.5);
    const tokenOnly = tokens.colors.text.disabled;
    const bg = tokens.colors.bg.level3;

    expect(contrastRatio(compounded, bg)).toBeLessThan(2.5);
    expect(contrastRatio(tokenOnly, bg)).toBeGreaterThan(contrastRatio(compounded, bg));
    expect(contrastRatio(tokenOnly, bg)).toBeGreaterThanOrEqual(3.0);
  });
});

/**
 * The classification, as code.
 *
 * Three prior spot-fixes (#4182, #4451, and this sweep) each re-derived which
 * `text.disabled` uses are legitimate. This allowlist records the answer so a new
 * usage has to be justified rather than silently added, and so the next audit
 * does not re-litigate the same sites.
 */
const ALLOWED_DISABLED_USAGES: Record<string, string> = {
  // Token plumbing — definitions and aliases, not usages.
  'design-system/tokens/colors.ts': 'the token definition itself',
  'theme/semanticTheme.ts': 'aliases the token as themeVars.textDisabled',
  'theme/themeConfig.ts': "MUI palette text.disabled — the framework's own disabled slot",
  'styles/globalStyles.ts': 'exposes the token as a CSS custom property',

  // Genuinely-inactive controls: WCAG 2.1 SC 1.4.3 exempts inactive components,
  // and the fade is the state indicator.
  'components/player/PlaybackControls.tsx': 'disabled transport buttons (isDisabled ? ...)',
  'components/player/VolumeControl.tsx': 'disabled mute button (disabled ? ...)',
  'components/shared/ContextMenu/ContextMenu.styles.ts': '&.Mui-disabled menu item',

  // Icons and decoration carry no text contrast requirement.
  'components/shared/DropZone/DropZoneIcon.tsx': 'decorative upload icon',
  'components/shared/DropZone/DropZoneStyles.ts': 'alpha(...) border tint, not text',
  'components/settings/FoldersList.tsx': 'decorative FolderOpenIcon',

  // Unreachable branch: the four real toast types all return a semantic colour.
  'components/shared/Toast/toastColors.ts': 'default: fallback for an unknown toast type',
};

describe('no new normal-text use of text.disabled creeps back in (#4635)', () => {
  it('every text.disabled / textDisabled usage is on the reviewed allowlist', async () => {
    const modules = import.meta.glob('/src/**/*.{ts,tsx}', {
      query: '?raw',
      import: 'default',
      eager: true,
    }) as Record<string, string>;

    const offenders: string[] = [];

    // Strip comments first. Every one of these fixes left a comment explaining
    // what `text.disabled` used to be here and why it moved — matching those
    // would flag the documentation of the fix as the defect.
    const stripComments = (src: string) =>
      src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/[^\n]*/g, '');

    for (const [path, source] of Object.entries(modules)) {
      if (path.includes('__tests__') || path.includes('/test/')) continue;
      if (!/\btext\.disabled\b|\btextDisabled\b/.test(stripComments(source))) continue;

      const rel = path.replace(/^\/src\//, '');
      const allowed = Object.keys(ALLOWED_DISABLED_USAGES).some((k) => rel.endsWith(k));
      if (!allowed) offenders.push(rel);
    }

    expect(offenders).toEqual([]);
  });
});
