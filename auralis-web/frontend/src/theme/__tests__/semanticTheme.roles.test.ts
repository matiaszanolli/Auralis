/**
 * Semantic theme glass/menu/switch roles — light-mode contrast (#5641)
 *
 * Five surfaces (batch "more" menu, add-to-playlist menu, Similar Tracks
 * modal, track-card duration badge, album-pane Auto-Mastering switch) used to
 * fill their background from fixed dark-only glass/gradient/white-alpha
 * tokens while their child text came from themeVars — dark ink on a dark fill
 * (or white on white) in light mode.
 *
 * The roles now resolve per mode. Dark mode must keep the exact pre-fix
 * values (appearance unchanged), and light mode must meet WCAG AA: 4.5:1 for
 * text on its fill, 3:1 for the switch thumb against its track. Glass fills
 * are semi-transparent, so the light-mode assertions compose each fill over
 * both worst-case artwork backdrops (black and white) before measuring.
 */

import { describe, expect, it } from 'vitest';
import { tokens } from '@/design-system/tokens';
import { getSemanticTheme, type SemanticTheme, type ThemeMode } from '../semanticTheme';

/** Parse `#rgb`/`#rrggbb`/`rgb()`/`rgba()` into [r, g, b, a] (0-255 / 0-1). */
function parseColor(value: string): [number, number, number, number] {
  const hex = value.trim();
  if (hex.startsWith('#')) {
    const body = hex.slice(1);
    const full = body.length === 3 ? body.split('').map((c) => c + c).join('') : body;
    return [
      parseInt(full.slice(0, 2), 16),
      parseInt(full.slice(2, 4), 16),
      parseInt(full.slice(4, 6), 16),
      1,
    ];
  }
  const m = value.match(/rgba?\(([^)]+)\)/);
  if (!m) throw new Error(`Unsupported color: ${value}`);
  const [r, g, b, a = '1'] = m[1].split(',').map((part) => part.trim());
  return [Number(r), Number(g), Number(b), Number(a)];
}

/** Composite an rgba color over an opaque backdrop, returning 0-1 channels. */
function compositeOver(color: string, backdrop: [number, number, number]): [number, number, number] {
  const [r, g, b, a] = parseColor(color);
  const mix = (c: number, bg: number) => (c / 255) * a + bg * (1 - a);
  return [mix(r, backdrop[0]), mix(g, backdrop[1]), mix(b, backdrop[2])];
}

/** WCAG relative luminance of linearly-composited 0-1 channels. */
function luminance([r, g, b]: [number, number, number]): number {
  const [sr, sg, sb] = [r, g, b].map((c) => {
    const v = Math.min(1, Math.max(0, c));
    return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * sr + 0.7152 * sg + 0.0722 * sb;
}

/** Opaque channels of a color, or its composite over `backdrop` when given. */
function channels(color: string, backdrop?: [number, number, number]): [number, number, number] {
  const [r, g, b, a] = parseColor(color);
  if (backdrop) return compositeOver(color, backdrop);
  if (a < 1) throw new Error(`semi-transparent color ${color} needs a backdrop`);
  return [(r / 255), (g / 255), (b / 255)];
}

/** WCAG contrast ratio between a foreground and background color. */
function contrast(foreground: string, background: string, backdrop?: [number, number, number]): number {
  const l1 = luminance(channels(foreground, backdrop));
  const l2 = luminance(channels(background, backdrop));
  const [hi, lo] = l1 >= l2 ? [l1, l2] : [l2, l1];
  return (hi + 0.05) / (lo + 0.05);
}

/** Opaque color as 0-1 channels. */
function toChannels(color: string): [number, number, number] {
  const [r, g, b] = parseColor(color);
  return [r / 255, g / 255, b / 255];
}

const WHITE: [number, number, number] = [1, 1, 1];
const BLACK: [number, number, number] = [0, 0, 0];

/** Dark-mode pin: these roles must resolve to exactly the pre-#5641 values. */
const DARK_PIN: Record<string, string> = {
  menuSurface: 'linear-gradient(180deg, #1B232E 0%, #131A24 100%)',
  glassFillStrong: 'rgba(21, 29, 47, 0.55)',
  glassFill: 'rgba(21, 29, 47, 0.50)',
  glassFillHover: 'rgba(21, 29, 47, 0.70)',
  switchThumb: 'rgba(255, 255, 255, 0.50)',
  switchTrack: 'rgba(255, 255, 255, 0.15)',
};

describe('glass/menu/switch semantic roles (#5641)', () => {
  it('dark mode keeps the exact pre-fix values', () => {
    const dark = getSemanticTheme('dark');
    for (const [role, expected] of Object.entries(DARK_PIN)) {
      expect(dark[role as keyof SemanticTheme]).toBe(expected);
    }
  });

  it('both modes define every role', () => {
    const roles = Object.keys(DARK_PIN) as (keyof SemanticTheme)[];
    for (const mode of ['light', 'dark'] as ThemeMode[]) {
      const theme = getSemanticTheme(mode);
      for (const role of roles) {
        expect(typeof theme[role]).toBe('string');
        expect((theme[role] as string).length).toBeGreaterThan(0);
      }
    }
  });

  it('light mode menu text meets 4.5:1 on the menu surface', () => {
    const light = getSemanticTheme('light');
    // menuSurface is opaque in both modes, so no compositing backdrop needed.
    expect(contrast(light.textStrong, light.menuSurface)).toBeGreaterThanOrEqual(4.5);
    expect(contrast(light.textMuted, light.menuSurface)).toBeGreaterThanOrEqual(4.5);
    expect(contrast(light.textSecondary, light.menuSurface)).toBeGreaterThanOrEqual(4.5);
  });

  it('light mode modal text meets 4.5:1 on the strong glass fill over the app', () => {
    const light = getSemanticTheme('light');
    // The modal covers the app canvas, optionally dimmed by MUI's dialog
    // scrim (rgba(0,0,0,0.5)) — not by arbitrary artwork.
    const canvas = toChannels(light.canvas);
    const scrimmed = canvas.map((c) => c * 0.5) as [number, number, number];
    for (const backdrop of [canvas, scrimmed]) {
      expect(contrast(light.textPrimary, light.glassFillStrong, backdrop)).toBeGreaterThanOrEqual(4.5);
      expect(contrast(light.textSecondary, light.glassFillStrong, backdrop)).toBeGreaterThanOrEqual(4.5);
    }
  });

  it('light mode duration-badge text meets 4.5:1 at rest and on hover over any artwork', () => {
    const light = getSemanticTheme('light');
    for (const backdrop of [BLACK, WHITE]) {
      expect(contrast(light.textMuted, light.glassFill, backdrop)).toBeGreaterThanOrEqual(4.5);
      expect(contrast(light.textPrimary, light.glassFillHover, backdrop)).toBeGreaterThanOrEqual(4.5);
    }
  });

  it('light mode switch thumb meets 3:1 against its track', () => {
    const light = getSemanticTheme('light');
    // The switch sits on the album pane — the themed canvas, not artwork.
    const canvas = toChannels(light.canvas);
    expect(contrast(light.switchThumb, light.switchTrack, canvas)).toBeGreaterThanOrEqual(3);
  });
});

/** Dark-mode pin for the fill roles: the white-alphas the components used before (#6056). */
const FILL_DARK_PIN: Record<string, string> = {
  panelFill: 'rgba(255, 255, 255, 0.03)',
  hoverFill: 'rgba(255, 255, 255, 0.04)',
  selectedFill: 'rgba(255, 255, 255, 0.08)',
  onAccentDisabled: 'rgba(255, 255, 255, 0.50)',
};

describe('fill and disabled-label semantic roles (#6056)', () => {
  const light = getSemanticTheme('light');
  const canvas = toChannels(light.canvas);
  const raised = toChannels(light.surfaceRaised);

  it('dark mode keeps the exact white-alpha values the components used', () => {
    const dark = getSemanticTheme('dark');
    for (const [role, expected] of Object.entries(FILL_DARK_PIN)) {
      expect(dark[role as keyof SemanticTheme]).toBe(expected);
    }
  });

  it('both modes define every role, and light never reuses a white-alpha', () => {
    for (const role of Object.keys(FILL_DARK_PIN) as (keyof SemanticTheme)[]) {
      for (const mode of ['light', 'dark'] as ThemeMode[]) {
        expect(getSemanticTheme(mode)[role].length).toBeGreaterThan(0);
      }
      // White-alpha on the #FFFFFF / #F8F9FD palette is invisible - the bug.
      expect(light[role]).not.toMatch(/rgba\(255, 255, 255/);
    }
  });

  it.each(['panelFill', 'hoverFill', 'selectedFill'] as const)(
    'light mode %s is visible on the canvas and raised surfaces and keeps text >= 4.5:1',
    (role) => {
      for (const backdrop of [canvas, raised]) {
        const opaque = `rgb(${backdrop.map((c) => Math.round(c * 255)).join(', ')})`;
        // Distinguishable from the surface it sits on.
        expect(contrast(light[role], opaque, backdrop)).toBeGreaterThanOrEqual(1.05);
        // Text on the fill.
        expect(contrast(light.textPrimary, light[role], backdrop)).toBeGreaterThanOrEqual(4.5);
        expect(contrast(light.textSecondary, light[role], backdrop)).toBeGreaterThanOrEqual(4.5);
      }
    }
  );

  it('light mode selected segments differ from hover and panel by fill, not only by text colour', () => {
    expect(contrast(light.selectedFill, light.hoverFill, canvas)).toBeGreaterThanOrEqual(1.05);
    expect(contrast(light.selectedFill, light.panelFill, canvas)).toBeGreaterThanOrEqual(1.05);
  });

  it('light mode disabled accent-button label meets 3:1 on the disabled fill', () => {
    // Button.styles' :disabled state: accent.strong fill, over the themed canvas.
    for (const backdrop of [canvas, raised]) {
      expect(
        contrast(light.onAccentDisabled, tokens.colors.opacityScale.accent.strong, backdrop)
      ).toBeGreaterThanOrEqual(3);
    }
  });

  it('light mode secondary and muted text meet 4.5:1 on the settings-card surface', () => {
    // ScanStatusCard / FingerprintCoverageCard sit on surfaceTranslucent over the canvas.
    for (const backdrop of [canvas, raised]) {
      expect(contrast(light.textSecondary, light.surfaceTranslucent, backdrop)).toBeGreaterThanOrEqual(4.5);
      expect(contrast(light.textMuted, light.surfaceTranslucent, backdrop)).toBeGreaterThanOrEqual(4.5);
    }
  });
});
