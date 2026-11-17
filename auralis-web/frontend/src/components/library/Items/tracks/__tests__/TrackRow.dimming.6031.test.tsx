/**
 * Playback-dominance dimming never fades row text (#6031)
 *
 * Non-current rows used to take `opacity: 0.6` as a whole while anything plays, which
 * composited the artist/album/duration text down to 2.5-3.9:1 (below WCAG AA), and the
 * metadata's own 0.7 compounded it. Only the artwork dims now; it is undimmed on hover and
 * keyboard focus. The rules are read from the emotion stylesheet, since jsdom does not
 * resolve the attribute selector for getComputedStyle.
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@/test/test-utils';
import { RowContainer, TrackArtist, TrackAlbum } from '../TrackRow.styles';

function emotionCss(): string {
  return Array.from(document.querySelectorAll('style'))
    .map((el) => el.textContent ?? '')
    .join('\n');
}

describe('TrackRow dimming (#6031)', () => {
  it('dims only the artwork of a non-current row, never the row itself', () => {
    render(<RowContainer iscurrent="false" />);
    const css = emotionCss();

    expect(css).toMatch(/\[data-any-playing="true"\][^{]*\.track-row-art\{[^}]*opacity:0\.6/);
    const dimmed = [...css.matchAll(/(\[data-any-playing="true"\][^{]*)\{[^}]*opacity:0\.6/g)].map((m) => m[1]);
    expect(dimmed.length).toBeGreaterThan(0);
    for (const selector of dimmed) expect(selector).toContain('.track-row-art');
  });

  it('undims the artwork on :hover and :focus-within', () => {
    render(<RowContainer iscurrent="false" />);
    const css = emotionCss();

    expect(css).toMatch(/:hover \.track-row-art\{[^}]*opacity:1/);
    expect(css).toMatch(/:focus-within \.track-row-art\{[^}]*opacity:1/);
  });

  it('adds no opacity to the artist or album text', () => {
    render(<><TrackArtist>a</TrackArtist><TrackAlbum>b</TrackAlbum></>);

    expect(getComputedStyle(screen.getByText('a')).opacity).not.toBe('0.7');
    expect(getComputedStyle(screen.getByText('b')).opacity).not.toBe('0.7');
  });
});
