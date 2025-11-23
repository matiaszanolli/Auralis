/**
 * SimilarTracksLoadingState Component Tests
 *
 * Tests for loading state display:
 * - Loading spinner visibility
 * - Loading message display
 */

import { vi } from 'vitest';
import { render, screen } from '@/test/test-utils';
import { SimilarTracksLoadingState } from '../SimilarTracksLoadingState';

describe('SimilarTracksLoadingState', () => {
  it('should render loading spinner', () => {
    const { container } = render(<SimilarTracksLoadingState />);

    // Check for CircularProgress
    const spinner = container.querySelector('svg');
    expect(spinner).toBeInTheDocument();
  });

  it('should display loading message', () => {
    render(<SimilarTracksLoadingState />);

    expect(screen.getByText('Finding similar tracks...')).toBeInTheDocument();
  });

  it('should have proper structure', () => {
    const { container } = render(<SimilarTracksLoadingState />);

    const box = container.querySelector('[class*="MuiBox"]');
    expect(box).toBeInTheDocument();
  });

  it('should center align content', () => {
    const { container } = render(<SimilarTracksLoadingState />);

    const box = container.querySelector('[class*="MuiBox"]');
    expect(box).toBeInTheDocument();
  });
});
