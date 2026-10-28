/**
 * A dimmed track row returns to full opacity under keyboard focus (#6031)
 *
 * While anything plays, non-current rows are dimmed to 0.6. Hover restored full
 * opacity but keyboard focus did not, so a keyboard user navigated a list of
 * low-contrast rows. The rule is read from the emotion stylesheet, since jsdom
 * does not resolve the attribute selector for getComputedStyle.
 */

import { describe, it, expect } from 'vitest';
import { render } from '@/test/test-utils';
import { RowContainer } from '../TrackRow.styles';

function emotionCss(): string {
  return Array.from(document.querySelectorAll('style'))
    .map((el) => el.textContent ?? '')
    .join('\n');
}

describe('TrackRow dimming (#6031)', () => {
  it('restores full opacity on :focus-visible and :focus-within, as it does on :hover', () => {
    render(<RowContainer iscurrent="false" />);
    const css = emotionCss();

    expect(css).toMatch(/\[data-any-playing="true"\][^{]*\{[^}]*opacity:0\.6/);
    expect(css).toMatch(/:focus-visible\{[^}]*opacity:1/);
    expect(css).toMatch(/:focus-within\{[^}]*opacity:1/);
  });
});
