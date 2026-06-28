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

  it('--aurora-cyan/violet match the brand accent tokens (#4171)', () => {
    expect(cssVar('aurora-cyan').toUpperCase()).toBe(
      tokens.colors.accent.secondary.toUpperCase(),
    );
    expect(cssVar('aurora-violet').toUpperCase()).toBe(
      tokens.colors.accent.primary.toUpperCase(),
    );
  });

  it('--aurora gradients reference the token-aligned stop vars, not off-palette hex (#4171)', () => {
    for (const name of ['aurora-gradient', 'aurora-horizontal', 'aurora-vertical']) {
      const value = cssVar(name);
      expect(value).toContain('var(--aurora-cyan)');
      expect(value).toContain('var(--aurora-violet)');
      expect(value).toContain('var(--aurora-pink)');
      // The old Tailwind cyan/pink must be gone.
      expect(value.toUpperCase()).not.toContain('#06B6D4');
      expect(value.toUpperCase()).not.toContain('#F472B6');
    }
  });

  it('--space-* match tokens.spacing (no legacy 4-8px grid drift) (#4172)', () => {
    expect(cssVar('space-xs')).toBe(tokens.spacing.xs);   // 4px
    expect(cssVar('space-sm')).toBe(tokens.spacing.sm);   // 6px
    expect(cssVar('space-md')).toBe(tokens.spacing.md);   // 12px
    expect(cssVar('space-lg')).toBe(tokens.spacing.lg);   // 20px
    expect(cssVar('space-xl')).toBe(tokens.spacing.xl);   // 28px
    expect(cssVar('space-2xl')).toBe(tokens.spacing.xxl); // 40px
    expect(cssVar('space-3xl')).toBe(tokens.spacing.xxxl); // 56px
  });

  it('the no-token --space-base var has been removed (#4172)', () => {
    expect(() => cssVar('space-base')).toThrow();
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
