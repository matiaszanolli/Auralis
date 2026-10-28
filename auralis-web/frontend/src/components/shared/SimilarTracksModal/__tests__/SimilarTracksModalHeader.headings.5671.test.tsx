/**
 * Heading structure of the dialog title and the queue (#5671)
 *
 * MUI's DialogTitle already renders the dialog's <h2>; the header nested an <h6> and a <p> inside
 * it, which is invalid HTML and made the heading outline unreadable. The queue's <h3> had no <h2>
 * above it.
 */

import { describe, it, expect, vi } from 'vitest';
import { render } from '@/test/test-utils';
import { screen } from '@testing-library/react';
import { SimilarTracksModalHeader } from '../SimilarTracksModalHeader';

describe('SimilarTracksModalHeader (#5671)', () => {
  it('is one heading with no heading or paragraph nested inside it', () => {
    const { container } = render(<SimilarTracksModalHeader trackTitle="Oktubre" onClose={vi.fn()} />);

    const headings = screen.getAllByRole('heading');
    expect(headings).toHaveLength(1);
    expect(headings[0].tagName).toBe('H2');
    expect(headings[0]).toHaveTextContent('Similar Tracks');
    expect(headings[0]).toHaveTextContent('Tracks similar to "Oktubre"');
    expect(container.querySelectorAll('h2 h1, h2 h2, h2 h3, h2 h4, h2 h5, h2 h6, h2 p')).toHaveLength(0);
  });
});
