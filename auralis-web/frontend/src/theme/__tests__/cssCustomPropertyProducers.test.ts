/**
 * Every CSS custom property consumed by a CSS module must have a producer (#4535).
 *
 * `ShuffleModeSelector.module.css` referenced ten custom properties
 * (--bg-secondary, --bg-tertiary, --text-primary, --text-primary-full,
 * --text-secondary, --accent-primary, --accent-dark, --spacing-*,
 * --border-radius-*, --font-size-*) that are defined nowhere in the repo. Each
 * was written as `var(--name, <dark fallback>)`, so CSS silently used the
 * fallback and the component rendered as a fixed dark island that ignored the
 * light/dark toggle entirely. Nothing failed loudly — the fallback *is* the
 * failure mode.
 *
 * The only producer of CSS custom properties in this app is
 * `getSemanticCssVariables()`, written onto the document root by ThemeContext
 * (the `--app-*` set, re-resolved per theme mode). `src/index.css` used to be
 * listed as a second, "static" producer — but it has not been imported since
 * be0f3619 (2025-11-22), so nothing it declared ever shipped; both it and its
 * only consumer (ShuffleModeSelector) are deleted (#5642).
 *
 * A `var()` naming anything else resolves to its fallback forever, which means
 * it cannot react to the theme. This guard is repo-wide so the next CSS module
 * cannot reintroduce the class.
 */

import { describe, it, expect } from 'vitest';
import { getSemanticCssVariables } from '../semanticTheme';
import { globalStyles } from '@/styles/globalStyles';

// Every CSS module in the app, keyed by path. `eager` so this stays synchronous.
const cssModules = import.meta.glob('../../**/*.module.css', {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>;

/** Custom properties produced by the theme contract (identical keys per mode). */
function semanticProducers(): Set<string> {
  return new Set(Object.keys(getSemanticCssVariables('dark')));
}

/** Strip `/* ... *\/` blocks so prose describing a var is not read as a use. */
function stripComments(css: string): string {
  return css.replace(/\/\*[\s\S]*?\*\//g, '');
}

/** `var(--name` references in a stylesheet, ignoring commentary. */
function consumedVars(css: string): string[] {
  return [...stripComments(css).matchAll(/var\(\s*(--[a-zA-Z0-9-]+)/g)].map((m) => m[1]);
}

const producers = semanticProducers();

describe('CSS custom property producers (#4535)', () => {
  it('discovers the CSS modules it claims to guard', () => {
    // #5642: ShuffleModeSelector.module.css — the tree's last CSS module — was
    // deleted, so there are no subjects and the it.each below runs zero times.
    // This pin is a tripwire, not decoration: adding the first .module.css
    // fails it, forcing whoever adds the module to remove the pin and put the
    // file back under the orphan scan (proven live by the "guards the guard"
    // test below) instead of letting the scan go silently vacuous.
    expect(Object.keys(cssModules)).toEqual([]);
  });

  it('the theme contract is the only producer and is non-empty', () => {
    expect(producers.size).toBeGreaterThan(0);
    expect([...producers].every((name) => name.startsWith('--app-'))).toBe(true);
  });

  it.each(Object.keys(cssModules))('%s references only produced properties', (path) => {
    const orphans = [...new Set(consumedVars(cssModules[path]))]
      .filter((name) => !producers.has(name))
      .sort();

    expect(orphans, `${path} consumes custom properties with no producer. Use an --app-* var from getSemanticCssVariables().`).toEqual([]);
  });

  it('a module consuming a var outside the contract would fail (guards the guard)', () => {
    // Pins the orphan detection itself: an --space-style name with no producer
    // must be reported, not silently resolved to a fallback (#5642's failure
    // mode — index.css "produced" vars nothing ever shipped).
    const orphanCss = '.x { gap: var(--space-md); }';
    const orphans = [...new Set(consumedVars(orphanCss))].filter((name) => !producers.has(name));
    expect(orphans).toEqual(['--space-md']);
  });

  it('the --app-* set is identical across modes, so no var goes unresolved on toggle', () => {
    expect(Object.keys(getSemanticCssVariables('light')).sort()).toEqual(
      Object.keys(getSemanticCssVariables('dark')).sort(),
    );
  });

  it('the :root defaults in globalStyles are generated from the contract, not hand-typed (#6057)', () => {
    // A hand-typed list drifted by six roles once; anything rendering before
    // ThemeProvider's layout effect resolved those to `unset`.
    const rootBlock = /:root\s*\{([\s\S]*?)\n  \}/.exec(globalStyles.styles)![1];
    const declared = [...rootBlock.matchAll(/(--app-[a-z0-9-]+)\s*:/g)].map((m) => m[1]).sort();

    expect(declared).toEqual(Object.keys(getSemanticCssVariables('dark')).sort());
  });
});
