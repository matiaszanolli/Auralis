/**
 * index.css CSS-variable / token parity (#3927 / DS-1)
 *
 * The :root CSS variables in index.css had drifted from the design tokens
 * (border-radius scale, --silver text color, --aurora-pink, transition easing).
 * CSS can't import the TS tokens, so this test parses index.css and pins the
 * flagged variables to the canonical token values, guarding against future
 * drift.
 */

import { describe, it, expect } from 'vitest';
import { tokens } from '@/design-system';
// Vite raw import (typed via vite/client) — avoids node:fs and its type deps.
import indexCss from '../../index.css?raw';

/** Read a `--name: value;` declaration from the :root block. */
function cssVar(name: string): string {
  const m = indexCss.match(new RegExp(`--${name}\\s*:\\s*([^;]+);`));
  if (!m) throw new Error(`CSS variable --${name} not found in index.css`);
  return m[1].trim();
}

describe('index.css token parity (#3927)', () => {
  it('--radius-sm/md/lg match tokens.borderRadius.sm/md/lg', () => {
    expect(cssVar('radius-sm')).toBe(tokens.borderRadius.sm); // 8px
    expect(cssVar('radius-md')).toBe(tokens.borderRadius.md); // 12px
    expect(cssVar('radius-lg')).toBe(tokens.borderRadius.lg); // 16px
  });

  it('--silver matches tokens.colors.text.secondary (no off-brand slate)', () => {
    expect(cssVar('silver')).toBe(tokens.colors.text.secondary);
    expect(cssVar('silver').toUpperCase()).not.toContain('#E2E8F0');
  });

  it('--aurora-pink matches tokens.colors.audioSemantic.harmonic', () => {
    expect(cssVar('aurora-pink').toUpperCase()).toBe(
      tokens.colors.audioSemantic.harmonic.toUpperCase(),
    );
  });

  it('transition vars use brand cubic-bezier easing, not plain ease', () => {
    for (const name of ['transition-fast', 'transition-normal', 'transition-slow']) {
      const value = cssVar(name);
      expect(value).toContain('cubic-bezier');
      // plain `ease` / `ease-in-out` keyword must be gone
      expect(value).not.toMatch(/\bease(-in-out|-in|-out)?\b/);
    }
  });
});
