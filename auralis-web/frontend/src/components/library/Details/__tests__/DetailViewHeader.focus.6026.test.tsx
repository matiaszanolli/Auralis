/**
 * Opening a detail view moves focus to its heading (#6026)
 *
 * The grid is replaced, so the activated card unmounted and focus fell to <body>
 * with nothing announcing the new view.
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@/test/test-utils';
import { DetailViewHeader } from '../DetailViewHeader';

describe('DetailViewHeader focus (#6026)', () => {
  it('focuses the level-one heading when the view opens', () => {
    render(<DetailViewHeader artwork={<div />} title="Abbey Road" subtitle="The Beatles" />);

    const heading = screen.getByRole('heading', { level: 1, name: 'Abbey Road' });
    expect(heading).toHaveFocus();
    expect(heading).toHaveAttribute('tabindex', '-1'); // focusable by script, not a Tab stop
  });
});
