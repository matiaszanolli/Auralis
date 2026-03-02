/**
 * SimilarTracksErrorState Component Tests
 *
 * Tests for error state display:
 * - Error message rendering
 * - Alert component visibility
 */

import { render, screen } from '@/test/test-utils';
import { SimilarTracksErrorState } from '../SimilarTracksErrorState';

describe('SimilarTracksErrorState', () => {
  it('should display error message', () => {
    render(
      <SimilarTracksErrorState error="Failed to load similar tracks" />
    );

    expect(screen.getByText('Failed to load similar tracks')).toBeInTheDocument();
  });

  it('should render alert component', () => {
    const { container } = render(
      <SimilarTracksErrorState error="Network error" />
    );

    const alert = container.querySelector('[role="alert"]');
    expect(alert).toBeInTheDocument();
  });

  it('should handle different error messages', () => {
    const errors = [
      'Failed to load similar tracks',
      'Network timeout',
      'Invalid track ID',
      'Server error: 500',
    ];

    errors.forEach((error) => {
      const { unmount } = render(
        <SimilarTracksErrorState error={error} />
      );

      expect(screen.getByText(error)).toBeInTheDocument();
      unmount();
    });
  });

  it('should handle long error messages', () => {
    const longError = 'A very long error message that explains what went wrong in detail and might wrap to multiple lines';

    render(
      <SimilarTracksErrorState error={longError} />
    );

    expect(screen.getByText(longError)).toBeInTheDocument();
  });

  it('should handle special characters in error message', () => {
    const specialError = 'Error: "Failed" & <retry> required';

    render(
      <SimilarTracksErrorState error={specialError} />
    );

    expect(screen.getByText(specialError)).toBeInTheDocument();
  });
});
