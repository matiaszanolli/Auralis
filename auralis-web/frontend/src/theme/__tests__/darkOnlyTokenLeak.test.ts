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
 * A repo sweep originally found 324 such references across 104 files. That
 * migration is now COMPLETE, so this guard changed shape: it used to be an
 * allowlist of converted files (`MIGRATED`, extended as work progressed), and
 * is now a repo-wide assertion that no production source reads these
 * primitives at all. That is strictly stronger — the allowlist could only
 * protect files someone remembered to add, so a brand-new component
 * reintroducing the bug was invisible to it. This is the "forbid new usage"
 * CI check #4877's own test plan asked for.
 *
 * A grep-style source assertion rather than a render test on purpose: the
 * defect is a *source-level* reference to a dark-only constant. Under jsdom a
 * `var(--app-text-primary)` never resolves to a real color, so a computed-style
 * assertion would pass for both the fixed and broken versions and prove
 * nothing.
 */

import { describe, expect, it } from 'vitest';

/**
 * The only modules allowed to read the dark-only primitives.
 *
 * `semanticTheme.ts` is the mapping layer whose entire job is to bind
 * primitives to semantic names per mode; `themeConfig.ts` does the same for
 * the MUI palette. Every other consumer must go through `themeVars`.
 */
// Matched by basename: import.meta.glob normalises keys to the SHORTEST
// relative path, so semanticTheme.ts arrives as '../semanticTheme.ts', not
// '../../theme/semanticTheme.ts'. Suffix-matching a directory path silently
// matches nothing, which would have made the exemption a no-op.
const MAPPING_LAYER = ['semanticTheme.ts', 'themeConfig.ts'];

const basename = (path: string): string => path.slice(path.lastIndexOf('/') + 1);

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

function isProductionSource(path: string): boolean {
  if (path.includes('__tests__') || /\.test\.tsx?$/.test(path)) return false;
  if (path.includes('/test/')) return false;
  return !MAPPING_LAYER.includes(basename(path));
}

const DARK_ONLY = /tokens\.colors\.(?:text|bg)\.[A-Za-z0-9]+/g;

describe('dark-only token leak (#4877)', () => {
  it('no production source reads a dark-only text/bg primitive', () => {
    const offenders: string[] = [];

    for (const [path, source] of Object.entries(sources)) {
      if (!isProductionSource(path)) continue;
      const hits = stripComments(source).match(DARK_ONLY);
      if (hits) offenders.push(`${path}: ${[...new Set(hits)].join(', ')}`);
    }

    // Named explicitly rather than counted: the failure message should tell you
    // which file and which token, not just that a number moved.
    expect(offenders).toEqual([]);
  });

  it('the sweep actually inspects the tree (guards against a broken glob)', () => {
    // If the glob pattern ever stops matching, every assertion above passes
    // vacuously. Pin that it sees a realistic number of modules and that a
    // known-migrated file is among them.
    const production = Object.keys(sources).filter(isProductionSource);
    expect(production.length).toBeGreaterThan(200);
    expect(
      production.some((p) => p.endsWith('/design-system/primitives/Button.tsx'))
    ).toBe(true);
  });

  it('the mapping layer is exempt but still present', () => {
    // If these files are ever renamed, the exemption silently starts covering
    // nothing — or worse, the mapping layer starts failing the sweep.
    for (const allowed of MAPPING_LAYER) {
      expect(Object.keys(sources).some((p) => basename(p) === allowed)).toBe(true);
    }
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

  it('the substitutions preserved dark-mode appearance', async () => {
    // Every replacement was taken from `darkSemanticTheme`, not eyeballed, so
    // dark mode must render identically to before the migration. Pinning the
    // identities that carried the bulk of the 169 rewrites.
    const { tokens } = await import('@/design-system/tokens');
    const { getSemanticTheme } = await import('../semanticTheme');
    const dark = getSemanticTheme('dark');

    expect(dark.textPrimary).toBe(tokens.colors.text.primary);
    expect(dark.textSecondary).toBe(tokens.colors.text.secondary);
    expect(dark.textMuted).toBe(tokens.colors.text.metadata);
    expect(dark.textDisabled).toBe(tokens.colors.text.disabled);
    expect(dark.textStrong).toBe(tokens.colors.text.primaryFull);
    expect(dark.canvas).toBe(tokens.colors.bg.level0);
    expect(dark.surfacePrimary).toBe(tokens.colors.bg.level1);
    expect(dark.surfaceSecondary).toBe(tokens.colors.bg.level2);
    expect(dark.surfaceRaised).toBe(tokens.colors.bg.level3);
    expect(dark.surfaceOverlay).toBe(tokens.colors.bg.level4);

    // The aliases relied on for `.tertiary` and the `bg` backwards-compat
    // names: identical strings, so those rewrites were value-preserving too.
    expect(tokens.colors.text.tertiary).toBe(tokens.colors.text.metadata);
    expect(tokens.colors.bg.primary).toBe(tokens.colors.bg.level0);
    expect(tokens.colors.bg.secondary).toBe(tokens.colors.bg.level1);
    expect(tokens.colors.bg.tertiary).toBe(tokens.colors.bg.level2);
    expect(tokens.colors.bg.elevated).toBe(tokens.colors.bg.level3);
  });
});
