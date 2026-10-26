/**
 * One scrollbar styling mechanism (#6058)
 *
 * Since Chromium 121 a non-`auto` `scrollbar-width` / `scrollbar-color` disables
 * every `::-webkit-scrollbar` pseudo-element, and globalStyles sets both on `*`.
 * The desktop shell pins Electron well past that, so any webkit scrollbar rule
 * is dead code that never renders. Keep the standard properties only.
 */

import { describe, it, expect } from 'vitest';
import { globalStyles } from '../globalStyles';

const sources = import.meta.glob('../../**/*.{ts,tsx,css}', {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>;

describe('scrollbar styling (#6058)', () => {
  it('globalStyles uses the standard scrollbar properties', () => {
    expect(globalStyles.styles).toContain('scrollbar-color');
    expect(globalStyles.styles).not.toContain('::-webkit-scrollbar');
  });

  it('no production source styles ::-webkit-scrollbar', () => {
    const offenders = Object.entries(sources)
      .filter(([path]) => !path.includes('__tests__') && !/\.test\.tsx?$/.test(path))
      .filter(([, source]) => source.includes('::-webkit-scrollbar'))
      .map(([path]) => path)
      .sort();

    expect(offenders).toEqual([]);
  });
});
