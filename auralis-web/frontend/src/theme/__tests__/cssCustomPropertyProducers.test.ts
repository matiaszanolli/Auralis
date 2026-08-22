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
 * There are exactly two producers of custom properties in this app:
 *   - `getSemanticCssVariables()`, written onto the document root by
 *     ThemeContext (the `--app-*` set, re-resolved per theme mode)
 *   - the `:root` block in `index.css` (static, mode-independent)
 *
 * A `var()` naming anything else resolves to its fallback forever, which means
 * it cannot react to the theme. This guard is repo-wide so the next CSS module
 * cannot reintroduce the class.
 */

import { describe, it, expect } from 'vitest';
import { getSemanticCssVariables } from '../semanticTheme';
import indexCss from '@/index.css?raw';

// Every CSS module in the app, keyed by path. `eager` so this stays synchronous.
const cssModules = import.meta.glob('../../**/*.module.css', {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>;

/** `--name:` declarations in index.css — the static producer set. */
function indexCssProducers(): Set<string> {
  const names = new Set<string>();
  for (const m of indexCss.matchAll(/(--[a-zA-Z0-9-]+)\s*:/g)) {
    names.add(m[1]);
  }
  return names;
}

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

const producers = new Set<string>([...indexCssProducers(), ...semanticProducers()]);

describe('CSS custom property producers (#4535)', () => {
  it('discovers the CSS modules it claims to guard', () => {
    // A glob that silently matches nothing would make every assertion below
    // vacuously true — the exact way this class of test rots.
    expect(Object.keys(cssModules).length).toBeGreaterThan(0);
  });

  it('both producer sets are non-empty', () => {
    expect(indexCssProducers().size).toBeGreaterThan(0);
    expect(semanticProducers().size).toBeGreaterThan(0);
  });

  it.each(Object.keys(cssModules))('%s references only produced properties', (path) => {
    const orphans = [...new Set(consumedVars(cssModules[path]))]
      .filter((name) => !producers.has(name))
      .sort();

    expect(orphans, `${path} consumes custom properties with no producer. Use an --app-* var from getSemanticCssVariables() or a var declared in index.css.`).toEqual([]);
  });

  it('the theme contract still produces the properties ShuffleModeSelector needs', () => {
    // Pins the specific names the #4535 rewrite moved onto, so removing one
    // from the contract fails here rather than silently un-theming the file.
    const semantic = semanticProducers();
    for (const name of [
      '--app-surface-secondary',
      '--app-surface-overlay',
      '--app-surface-raised',
      '--app-text-primary',
      '--app-text-secondary',
      '--app-accent',
      '--app-accent-hover',
      '--app-on-accent',
      '--app-border-subtle',
    ]) {
      expect(semantic).toContain(name);
    }
  });

  it('the --app-* set is identical across modes, so no var goes unresolved on toggle', () => {
    expect(Object.keys(getSemanticCssVariables('light')).sort()).toEqual(
      Object.keys(getSemanticCssVariables('dark')).sort(),
    );
  });
});
