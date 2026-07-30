/**
 * Dark-only color primitives must not be read directly by themed surfaces (#4877).
 *
 * `ThemeContext` states the contract: `themeVars` (and the `--app-*` custom
 * properties it publishes) is the only theme-aware color source, and the raw
 * `tokens.colors.*` primitives are dark-only build blocks not for direct
 * component use. `tokens.colors.text.primary` is a literal
 * `rgba(255,255,255,0.95)` with no light-mode branch, and light mode's canvas
 * is `#F8F9FD` — so a component reading it renders near-white text on a
 * near-white background.
 *
 * A repo sweep found 324 such references across 104 files. That migration is
 * sequenced (see #4877); this guard locks in the files already converted so
 * they cannot silently regress while the rest is worked through. Extend
 * `MIGRATED` as files are migrated — the list only ever grows.
 *
 * A grep-style source assertion rather than a render test on purpose: the
 * defect is a *source-level* reference to a dark-only constant. Under jsdom a
 * `var(--app-text-primary)` never resolves to a real color, so a computed-style
 * assertion would pass for both the fixed and broken versions and prove
 * nothing.
 */

import { describe, expect, it } from 'vitest';

/** Files converted to `themeVars`. Never remove an entry — only add. */
const MIGRATED = [
  // Design-system primitives first: fixing these propagates to every consumer.
  '../../design-system/primitives/Button.tsx',
  '../../design-system/primitives/Input.tsx',
  '../../design-system/primitives/IconButton.tsx',
  '../../design-system/primitives/Badge.tsx',
  '../../design-system/primitives/Slider.tsx',
  // Highest-reach library surfaces.
  '../../components/library/Items/tracks/TrackRow.styles.ts',
  '../../components/library/Items/tables/TrackTableRowItem.tsx',
] as const;

const sources = import.meta.glob('../../**/*.{ts,tsx}', {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>;

/** Strip comments so a token named in an explanatory note is not a hit. */
function stripComments(source: string): string {
  return source
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/(^|[^:])\/\/.*$/gm, '$1');
}

function sourceFor(relativePath: string): string {
  const key = Object.keys(sources).find((k) => k.endsWith(relativePath.replace('../../', '/')));
  if (!key) throw new Error(`fixture not found: ${relativePath}`);
  return sources[key];
}

describe('dark-only token leak (#4877)', () => {
  describe.each(MIGRATED)('%s', (file) => {
    it('reads no dark-only text primitive', () => {
      const code = stripComments(sourceFor(file));
      const hits = code.match(/tokens\.colors\.text\.[A-Za-z]+/g) ?? [];
      expect(hits).toEqual([]);
    });

    it('reads no dark-only background primitive', () => {
      const code = stripComments(sourceFor(file));
      const hits = code.match(/tokens\.colors\.bg\.[A-Za-z0-9]+/g) ?? [];
      expect(hits).toEqual([]);
    });

    it('imports themeVars', () => {
      expect(sourceFor(file)).toContain('themeVars');
    });
  });

  it('the dark-only primitives really are dark-only (the premise)', async () => {
    const { tokens } = await import('@/design-system/tokens');
    // If these ever gain a light-mode branch, this whole migration's rationale
    // changes and the issue should be revisited rather than silently continued.
    expect(tokens.colors.text.primary).toContain('255, 255, 255');
    expect(tokens.colors.text.secondary).toContain('255, 255, 255');
  });

  it('themeVars resolves through CSS custom properties, not literals', async () => {
    const { themeVars } = await import('../semanticTheme');
    expect(themeVars.textPrimary).toBe('var(--app-text-primary)');
    expect(themeVars.textSecondary).toBe('var(--app-text-secondary)');
    expect(themeVars.textMuted).toBe('var(--app-text-muted)');
  });

  it('both theme modes supply a distinct text color', async () => {
    const { getSemanticCssVariables } = await import('../semanticTheme');
    const dark = getSemanticCssVariables('dark');
    const light = getSemanticCssVariables('light');

    expect(dark['--app-text-primary']).toBeTruthy();
    expect(light['--app-text-primary']).toBeTruthy();
    // The bug in one line: a component hardcoding the dark primitive would
    // render the dark value in both modes.
    expect(light['--app-text-primary']).not.toBe(dark['--app-text-primary']);
  });
});
