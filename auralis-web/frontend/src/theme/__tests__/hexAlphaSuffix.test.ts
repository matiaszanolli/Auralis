/**
 * No hex-alpha suffix glued onto a colour token (#6055).
 *
 * `themeVars.*` values are `var(--app-...)` strings, so `${themeVars.x}80`
 * yields `var(--app-x)80` — an invalid declaration the browser drops, with no
 * error anywhere. The same concatenation on a hex token (`${tokens.colors.x}20`)
 * is valid but bypasses `opacityScale` / `withOpacity()` and ignores the theme.
 * For `var()` colours use `color-mix(in srgb, <colour> N%, transparent)`; for
 * hex tokens use `tokens.colors.opacityScale.*` or `withOpacity()`.
 *
 * A source-level assertion on purpose: under jsdom an unresolved `var(--x)80`
 * and a resolved colour are both just strings, so a render test cannot tell
 * the broken declaration from a working one.
 */

import { describe, expect, it } from 'vitest';

const sources = import.meta.glob('../../**/*.{ts,tsx}', {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>;

/** `${themeVars.x}NN` / `${tokens.colors.x.y}NN` inside a template literal. */
const HEX_ALPHA_SUFFIX = /\$\{(?:themeVars|tokens\.colors)\.[A-Za-z0-9_.]+\}[0-9a-fA-F]{2}\b/g;

const isProduction = (path: string): boolean =>
  !path.includes('__tests__') && !/\.(test|spec)\.tsx?$/.test(path);

describe('hex-alpha suffix on colour tokens (#6055)', () => {
  it('the pattern catches the broken shapes it exists for', () => {
    expect('`${themeVars.surfaceRaised}80`'.match(HEX_ALPHA_SUFFIX)).toEqual(['${themeVars.surfaceRaised}80']);
    expect('`0 0 8px ${tokens.colors.accent.primary}40`'.match(HEX_ALPHA_SUFFIX)).toEqual([
      '${tokens.colors.accent.primary}40',
    ]);
    // Not alpha: a unit, or a longer word.
    expect('`${tokens.colors.x}15px`'.match(HEX_ALPHA_SUFFIX)).toBeNull();
    expect('`${themeVars.x} 50%`'.match(HEX_ALPHA_SUFFIX)).toBeNull();
  });

  it('no production source appends a hex alpha to a themeVars or tokens.colors value', () => {
    const offenders = Object.entries(sources)
      .filter(([path]) => isProduction(path))
      .flatMap(([path, source]) => (source.match(HEX_ALPHA_SUFFIX) ?? []).map((hit) => `${path}: ${hit}`))
      .sort();

    expect(offenders).toEqual([]);
  });
});
