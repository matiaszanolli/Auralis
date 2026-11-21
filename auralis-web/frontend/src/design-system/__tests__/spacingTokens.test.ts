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
  // deleted src/performance/ wholesale. The 'components/shared/ui/
  // RadialPresetSelector.tsx' entry is gone the same way: it and its
  // supporting modules had zero production consumers and were deleted
  // (#4861 follow-up).

  // `margin: '0 auto'` is the horizontal-centering idiom, not a spacing value.
  // There is no token for `auto` and inventing one would obscure the intent.
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

  it('no template-literal padding/margin/gap re-types a spacing step (#6449)', async () => {
    // The scan above matches `padding: '` only, so a backtick value that mixes a token with a
    // literal equal to another step (`${tokens.spacing.sm} 12px`) slipped past it. A px literal
    // inside such a template is an offender when its value is a step of the scale; calc() offsets
    // (`calc(${tokens.spacing.md} - 3px)`) are arithmetic, not steps, and are skipped.
    const steps = new Set<string>(Object.values(tokens.spacing));
    const stepLiteralsIn = (source: string): string[] =>
      [...source.matchAll(/\b\w*(?:padding|Padding|margin|Margin|gap|Gap)\w*:\s*`([^`]*)`/g)]
        .map((m) => m[1])
        .filter((value) => !value.includes('calc('))
        .flatMap((value) => [...value.replace(/\$\{[^}]*\}/g, ' ').matchAll(/(?<![\w.-])\d+px\b/g)])
        .map((m) => m[0])
        .filter((px) => steps.has(px));

    // The scan sees what it exists for, and leaves alone what it must.
    expect(stepLiteralsIn('padding: `${tokens.spacing.sm} 12px`,')).toEqual(['12px']);
    expect(stepLiteralsIn('margin: `2px ${tokens.spacing.xs}`,')).toEqual(['2px']);
    expect(stepLiteralsIn('columnGap: `${tokens.spacing.sm} 4px`')).toEqual(['4px']);
    expect(stepLiteralsIn('padding: `${tokens.spacing.cluster} 48px`,')).toEqual([]); // off-scale, documented
    expect(stepLiteralsIn('paddingLeft: `calc(${tokens.spacing.md} - 4px)`,')).toEqual([]);
    expect(stepLiteralsIn('padding: `${tokens.spacing.sm} ${tokens.spacing.md}`,')).toEqual([]);
    expect(stepLiteralsIn("border: `1px solid ${tokens.colors.border.heavy}`,")).toEqual([]);

    const modules = import.meta.glob('/src/**/*.{ts,tsx}', {
      query: '?raw',
      import: 'default',
      eager: true,
    }) as Record<string, string>;
    const stripComments = (src: string) =>
      src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/[^\n]*/g, '');

    const offenders = Object.entries(modules)
      .filter(([path]) => !path.includes('__tests__') && !/\.test\.tsx?$/.test(path))
      .flatMap(([path, source]) =>
        stepLiteralsIn(stripComments(source)).map((px) => `${path.replace(/^\/src\//, '')}: ${px}`)
      );

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

/**
 * No doubled unit suffix after a px-valued token (#5644).
 *
 * The spacing/borderRadius scales are strings that already carry `px`
 * (`'12px'`), so `${tokens.spacing.md}px` emits `12pxpx`, which the browser
 * drops as invalid CSS. Four such sites shipped this way (MediaCardArtwork's
 * top-corner radius was visibly lost); the same class was fixed once before
 * in PlaylistList (#2357).
 */
describe('no doubled px after a px-valued token (#5644)', () => {
  it('no `${tokens.spacing|borderRadius.*}px` interpolation exists', async () => {
    const modules = import.meta.glob('/src/**/*.{ts,tsx}', {
      query: '?raw',
      import: 'default',
      eager: true,
    }) as Record<string, string>;

    const offenders: string[] = [];
    const doubled = /tokens\.(?:spacing|borderRadius)\.[A-Za-z0-9]+\}px/;

    for (const [path, source] of Object.entries(modules)) {
      if (path.includes('__tests__') || /\.test\.tsx?$/.test(path)) continue;
      if (doubled.test(source)) offenders.push(path.replace(/^\/src\//, ''));
    }

    expect(offenders).toEqual([]);
  });
});

/**
 * Literals that EQUAL a token must use it (#5648).
 *
 * After #5379/#5384/#4663 a residual set of sites still spelled out values the
 * scales already hold: `'8px'`/`'12px'`/`'16px'` radii (sm/md/lg), a 1.5
 * line-height (`typography.lineHeight.normal`), and `pulse 2s ease-in-out
 * infinite` (`animations.pulse`). Only EXACT matches are guarded here.
 *
 * Deliberate literals, recorded rather than tokenised (no visual change, no new
 * public scale step — decided in #5648):
 *  - 2/3/4/6px radii: the radius scale starts at 8px (sm). Those are skeleton
 *    bars, progress tracks and chips that are meant to be tighter than any
 *    component radius, so they stay literal.
 *  - letter-spacing outside the `tight` / `loose` steps (0.5px, 1px, 0.05em, -0.02em, 0.01em ...):
 *    uppercase labels, table headers and display text tracked to taste, each a one-off with no
 *    shared meaning, so no new step is minted for them (#6447).
 *  - 1.1 / 1.4 / 1.6 line-heights: between the 1.2 / 1.5 / 1.75 steps by design
 *    (a tight heading, dense row text, long-form description).
 *  - spin / rotate / shimmer / breathe / playbackShimmer durations: no animation
 *    token exists for them (only pulse does).
 *  - numeric `borderRadius: n` inside MUI `sx`: that is a THEME-SPACING MULTIPLE,
 *    not pixels, so it is not interchangeable with `tokens.borderRadius.*`.
 */
describe('values equal to a token use the token (#5648)', () => {
  const sources = (): Array<[string, string]> => {
    const modules = import.meta.glob('/src/**/*.{ts,tsx}', {
      query: '?raw',
      import: 'default',
      eager: true,
    }) as Record<string, string>;
    return Object.entries(modules).filter(
      ([path]) =>
        !path.includes('__tests__') &&
        !/\.test\.tsx?$/.test(path) &&
        !path.startsWith('/src/design-system/')
    );
  };

  const offenders = (pattern: RegExp) =>
    sources()
      .filter(([, source]) => pattern.test(source))
      .map(([path]) => path.replace(/^\/src\//, ''));

  it('no literal borderRadius equals tokens.borderRadius.sm / md / lg', () => {
    expect(offenders(/borderRadius:\s*['"](?:8|12|16)px['"]/)).toEqual([]);
  });

  it('no borderRadius reads the spacing scale (#6445)', () => {
    // Radii move with the radius scale, not the spacing scale; the literal guard above cannot see a
    // token-category mix-up, so this one matches the expression instead of a value.
    const wrongScale = /[Rr]adius[A-Za-z]*:[^,\n}]*tokens\.spacing\./;
    expect(offenders(wrongScale)).toEqual([]);

    expect(wrongScale.test('borderRadius: tokens.spacing.md,')).toBe(true);
    expect(wrongScale.test('borderRadius: `${tokens.spacing.xs} 0`,')).toBe(true);
    expect(wrongScale.test('borderRadius: tokens.borderRadius.md,')).toBe(false);
    expect(wrongScale.test("margin: tokens.spacing.xs, borderRadius: '4px',")).toBe(false);
  });

  it('no literal letterSpacing equals a typography.letterSpacing step (#6447)', () => {
    const exactMatch = /letterSpacing:\s*['"](?:-0\.01em|0\.02em)['"]/;
    expect(offenders(exactMatch)).toEqual([]);

    expect(exactMatch.test("letterSpacing: '-0.01em',")).toBe(true);
    expect(exactMatch.test('letterSpacing: "0.02em"')).toBe(true);
    expect(exactMatch.test("letterSpacing: '0.05em',")).toBe(false);
    expect(exactMatch.test('letterSpacing: tokens.typography.letterSpacing.tight,')).toBe(false);
  });

  it('no literal lineHeight equals a typography.lineHeight step', () => {
    expect(offenders(/lineHeight:\s*(?:1\.2|1\.5|1\.75)\s*[,}\n]/)).toEqual([]);
  });

  it('no `pulse 2s ease-in-out infinite` shorthand duplicates animations.pulse', () => {
    expect(offenders(/pulse\s+2s\s+(?:ease-in-out|cubic-bezier\(0\.4, 0, 0\.6, 1\))\s+infinite/)).toEqual([]);
  });

  it('the tokens those sites now read still hold the values they replaced', () => {
    expect([tokens.borderRadius.sm, tokens.borderRadius.md, tokens.borderRadius.lg]).toEqual([
      '8px',
      '12px',
      '16px',
    ]);
    expect([tokens.typography.letterSpacing.tight, tokens.typography.letterSpacing.loose]).toEqual([
      '-0.01em',
      '0.02em',
    ]);
    expect(tokens.typography.lineHeight.normal).toBe(1.5);
    expect(tokens.animations.pulse.duration).toBe('2s');
    expect(tokens.animations.pulse.timing).toBe('ease-in-out');
    expect(tokens.animations.pulse.iteration).toBe('infinite');
    expect(tokens.transitions.base).toBe('450ms');
    expect(tokens.transitions.easeInOut).toBe('cubic-bezier(0.4, 0, 0.6, 1)');
  });
});
