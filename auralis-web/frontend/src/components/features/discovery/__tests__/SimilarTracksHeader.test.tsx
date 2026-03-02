/**
 * SimilarTracksHeader Component Tests
 *
 * Tests for section header:
 * - Title display
 * - Description text
 * - Icon visibility
 */

import { render, screen } from '@/test/test-utils';
import { SimilarTracksHeader } from '../SimilarTracksHeader';

describe('SimilarTracksHeader', () => {
  it('should display section title', () => {
    render(<SimilarTracksHeader />);

    expect(screen.getByText('Similar Tracks')).toBeInTheDocument();
  });

  it('should display description text', () => {
    render(<SimilarTracksHeader />);

    expect(screen.getByText('Based on acoustic fingerprint analysis')).toBeInTheDocument();
  });

  it('should display icon', () => {
    const { container } = render(<SimilarTracksHeader />);

    // Check for sparkles icon (SVG)
    const icon = container.querySelector('svg');
    expect(icon).toBeInTheDocument();
  });

  it('should have proper structure', () => {
    render(<SimilarTracksHeader />);

    // Should have title and description
    const titleElement = screen.getByText('Similar Tracks');
    const descElement = screen.getByText('Based on acoustic fingerprint analysis');

    expect(titleElement).toBeInTheDocument();
    expect(descElement).toBeInTheDocument();
  });

  it('should render without props', () => {
    render(<SimilarTracksHeader />);

    expect(screen.getByText('Similar Tracks')).toBeInTheDocument();
    expect(screen.getByText('Based on acoustic fingerprint analysis')).toBeInTheDocument();
  });

  it('should have visual separation', () => {
    const { container } = render(<SimilarTracksHeader />);

    // Check for border element (divider)
    const elements = container.querySelectorAll('[class*="MuiBox"]');
    expect(elements.length).toBeGreaterThan(0);
  });

  it('should be accessible', () => {
    render(<SimilarTracksHeader />);

    const heading = screen.getByText('Similar Tracks');
    expect(heading).toBeInTheDocument();

    const description = screen.getByText('Based on acoustic fingerprint analysis');
    expect(description).toBeInTheDocument();
  });
});
