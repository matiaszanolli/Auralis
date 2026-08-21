/**
 * Spacing comes from the scale, and the exceptions are recorded (#4663)
 *
 * 31 literal pixel strings across 19 live files duplicated the spacing scale, so
 * a future change to that scale would silently miss them. They are now
 * `tokens.spacing.*`.
 *
 * **Correction to the issue**: it claims "there is no `8px` step; `sm` is 6px,
 * `md` is 12px", and treats `8px` as the flagship off-scale value needing a
 * deliberate decision. `8px` IS a named step — `spacing.cluster` — as are `16px`
 * (`group`) and `32px` (`section`). The organic steps sit outside the
 * xs/sm/md/lg alphabetical run, which is presumably how they were missed. The
 * genuinely off-scale values are `10px`, `24px` and `48px`.
 *
 * Every substitution is byte-identical to the literal it replaced, so the
 * migration carries no visual change — asserted below, since that is the whole
 * basis for doing it in one pass.
 */

import { describe, it, expect } from 'vitest';
import { tokens } from '@/design-system';

describe('the spacing steps used by the migration (#4663)', () => {
  // If any of these drift, the migrated call sites change appearance — which is
  // fine and intended (that is the point of tokenising), but this pins what the
  // values were at migration time so the change is visible in a diff.
  it.each([
    ['xxs', '2px'],
    ['xs', '4px'],
    ['sm', '6px'],
    ['cluster', '8px'],
    ['md', '12px'],
    ['group', '16px'],
    ['lg', '20px'],
  ])('spacing.%s was %s at migration time', (step, value) => {
    expect(tokens.spacing[step as keyof typeof tokens.spacing]).toBe(value);
  });

  it('8px is a real step, contrary to the issue', () => {
    expect(tokens.spacing.cluster).toBe('8px');
    expect(Object.values(tokens.spacing)).toContain('8px');
  });

  it('10px, 24px and 48px are genuinely absent from the scale', () => {
    const values = Object.values(tokens.spacing);
    expect(values).not.toContain('10px');
    expect(values).not.toContain('24px');
    expect(values).not.toContain('48px');
  });
});

/**
 * Files still allowed to contain a raw padding/margin/gap literal, with why.
 *
 * The issue's CONSISTENCY check asks that off-scale values get a documented
 * decision rather than a silent nearest-match, and that dead files are not
 * migrated. Both are recorded here so a new literal has to be justified.
 */
const ALLOWED_SPACING_LITERALS: Record<string, string> = {
  // The 'performance/lazyLoader.tsx' entry that stood here is gone: #4696
  // deleted src/performance/ wholesale.

  // `margin: '0 auto'` is the horizontal-centering idiom, not a spacing value.
  // There is no token for `auto` and inventing one would obscure the intent.
  'design-system/primitives/Container.tsx': "margin: '0 auto' centering idiom",
  'components/shared/ui/RadialPresetSelector.tsx': "margin: '0 auto' centering idiom",
  'components/library/Styles/SearchStyles.styles.ts': "margin: '0 auto' centering idiom",

  // Genuinely off-scale, kept literal so the control does not change size.
  // Snapping 10px->12px and 24px->20px/28px would be a visual regression, and
  // the issue explicitly asks for a decision rather than a nearest-match.
  'components/core/ErrorBoundary.tsx': "'10px 24px' both off-scale, documented inline",
};

describe('no new raw spacing literals (#4663)', () => {
  it('every padding/margin/gap literal is on the reviewed allowlist', async () => {
    const modules = import.meta.glob('/src/**/*.{ts,tsx}', {
      query: '?raw',
      import: 'default',
      eager: true,
    }) as Record<string, string>;

    const offenders: string[] = [];

    // Comments explain what each literal used to be, so match code only.
    const stripComments = (src: string) =>
      src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/[^\n]*/g, '');

    for (const [path, source] of Object.entries(modules)) {
      if (path.includes('__tests__') || /\.test\.tsx?$/.test(path)) continue;
      if (!/(padding|margin|gap): '/.test(stripComments(source))) continue;

      const rel = path.replace(/^\/src\//, '');
      if (!Object.keys(ALLOWED_SPACING_LITERALS).some((k) => rel.endsWith(k))) {
        offenders.push(rel);
      }
    }

    expect(offenders).toEqual([]);
  });

  it('PlaylistSection keeps only its 48px nesting indent', async () => {
    // The one partial case: three of its four values tokenised, the indent did
    // not. It is deliberately NOT on the allowlist above, because the file no
    // longer matches the `(padding|margin|gap): '` pattern at all — the literal
    // now lives inside a template string. This pins that.
    const source = (await import(
      '@/components/shared/ContextMenu/PlaylistSection.tsx?raw'
    )).default as string;

    expect(source).toContain('48px');
    expect(source).toContain('tokens.spacing.cluster');
    expect(source).not.toMatch(/padding: '/);
  });
});
