/**
 * themeConfig token-derivation regression tests
 *
 * #5384: MUI's numeric sx spacing maps onto tokens.spacing.
 * #5646: the parallel darkColors/lightColors palettes, the gradients
 *        re-export and the unused glassEffects helper are gone; the MUI
 *        success/error/warning/info palette is built straight from
 *        getSemanticTheme(mode) so it can no longer disagree with the
 *        semantic layer (dark palette.info used to be cyan #47D6FF while
 *        themeVars.info is the semantic blue).
 */

import { describe, it, expect } from 'vitest';
import { tokens, mediaBelow } from '@/design-system';
import { createAuralisTheme } from '../themeConfig';
import { getSemanticTheme, getSemanticCssVariables } from '../semanticTheme';
import * as themeConfigModule from '../themeConfig';

describe('MUI status palette derives from the semantic theme (#5646)', () => {
  it.each(['dark', 'light'] as const)('%s palette.{success,error,warning,info} equal getSemanticTheme(mode)', (mode) => {
    const theme = createAuralisTheme(mode);
    const semantic = getSemanticTheme(mode);
    expect(theme.palette.success.main).toBe(semantic.success);
    expect(theme.palette.error.main).toBe(semantic.error);
    expect(theme.palette.warning.main).toBe(semantic.warning);
    expect(theme.palette.info.main).toBe(semantic.info);
  });

  it.each(['dark', 'light'] as const)('%s palette.info agrees with the themeVars.info CSS variable', (mode) => {
    // themeVars.info is 'var(--app-info)'; the provider writes that variable
    // from getSemanticCssVariables(mode), so agreement means both resolve to
    // the same semantic value.
    const vars = getSemanticCssVariables(mode);
    expect(vars['--app-info']).toBe(createAuralisTheme(mode).palette.info.main);
  });
});

describe('the dead parallel colour APIs stay gone (#5646)', () => {
  it('themeConfig exports only the theme factory and the spacing unit', () => {
    expect(Object.keys(themeConfigModule).sort()).toEqual([
      'MUI_SPACING_UNIT_PX',
      'createAuralisTheme',
    ]);
  });

  it('the glass tokens that fed only glassEffects.backgroundDark are gone', () => {
    expect(tokens.glass.medium).not.toHaveProperty('backgroundDark');
    expect(tokens.glass.strong).not.toHaveProperty('backgroundDark');
    // backgroundLight survives — semanticTheme's light-mode glassFill roles
    // are built from it.
    expect(tokens.glass.medium.backgroundLight).toBe('rgba(255, 255, 255, 0.9)');
    expect(tokens.glass.strong.backgroundLight).toBe('rgba(255, 255, 255, 0.94)');
  });
});

describe('MUI numeric spacing derives from tokens.spacing (#5384)', () => {
  it.each(['dark', 'light'] as const)('%s theme maps spacing steps onto tokens', (mode) => {
    const theme = createAuralisTheme(mode);
    expect(theme.spacing(1)).toBe(tokens.spacing.cluster);
    expect(theme.spacing(2)).toBe(tokens.spacing.group);
    expect(theme.spacing(4)).toBe(tokens.spacing.section);
    expect(theme.spacing(0.5)).toBe(tokens.spacing.xs);
    expect(theme.spacing(1.5)).toBe(tokens.spacing.md);
  });

  it('keeps the rendered 8px unit (no visual change)', () => {
    expect(createAuralisTheme('dark').spacing(3)).toBe('24px');
  });
});

describe('MUI breakpoints derive from tokens.breakpoints (#6059)', () => {
  it.each(['dark', 'light'] as const)('%s theme breakpoint values equal the numeric tokens', (mode) => {
    const { values } = createAuralisTheme(mode).breakpoints;
    expect(values).toEqual({
      xs: Number.parseFloat(tokens.breakpoints.xs),
      sm: Number.parseFloat(tokens.breakpoints.sm),
      md: Number.parseFloat(tokens.breakpoints.md),
      lg: Number.parseFloat(tokens.breakpoints.lg),
      xl: Number.parseFloat(tokens.breakpoints.xl),
    });
  });

  it.each(['sm', 'md', 'lg', 'xl'] as const)(
    'mediaBelow(%s) is byte-identical to theme.breakpoints.down()',
    (key) => {
      expect(mediaBelow(key)).toBe(createAuralisTheme('dark').breakpoints.down(key));
    },
  );

  it('no production source uses an inclusive max-width on a breakpoint token', () => {
    const sources = import.meta.glob('../../**/*.{ts,tsx}', {
      query: '?raw',
      import: 'default',
      eager: true,
    }) as Record<string, string>;
    const offenders = Object.entries(sources)
      .filter(([path]) => !path.includes('__tests__') && !/\.test\.tsx?$/.test(path))
      .filter(([, source]) => /max-width:\s*\$\{tokens\.breakpoints\./.test(source))
      .map(([path]) => path);

    expect(offenders).toEqual([]);
  });
});
