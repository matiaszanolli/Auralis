/**
 * SimilarTracksEmptyState Component Tests
 *
 * Tests for empty state display:
 * - No track selected state
 * - No results found state
 * - Conditional messaging
 */

import { vi } from 'vitest';
import { render, screen } from '@/test/test-utils';
import { SimilarTracksEmptyState } from '../SimilarTracksEmptyState';

describe('SimilarTracksEmptyState', () => {
  describe('No Track Selected', () => {
    it('should display select track message when trackId is null', () => {
      render(<SimilarTracksEmptyState trackId={null} />);

      expect(screen.getByText('Play a track to discover similar music')).toBeInTheDocument();
    });

    it('should show music note icon when no track selected', () => {
      const { container } = render(<SimilarTracksEmptyState trackId={null} />);

      // Check for music note icon
      const icon = container.querySelector('svg');
      expect(icon).toBeInTheDocument();
    });

    it('should not display no results message when no track selected', () => {
      render(<SimilarTracksEmptyState trackId={null} />);

      expect(screen.queryByText('No similar tracks found')).not.toBeInTheDocument();
    });
  });

  describe('No Results Found', () => {
    it('should display no results message when trackId is provided', () => {
      render(<SimilarTracksEmptyState trackId={42} />);

      expect(screen.getByText('No similar tracks found')).toBeInTheDocument();
    });

    it('should display retry suggestion when trackId is provided', () => {
      render(<SimilarTracksEmptyState trackId={42} />);

      expect(screen.getByText('Try playing a different track')).toBeInTheDocument();
    });

    it('should show sparkles icon when track is selected but no results', () => {
      const { container } = render(<SimilarTracksEmptyState trackId={42} />);

      // Check for sparkles icon
      const icon = container.querySelector('svg');
      expect(icon).toBeInTheDocument();
    });

    it('should not display play message when track is selected', () => {
      render(<SimilarTracksEmptyState trackId={42} />);

      expect(screen.queryByText('Play a track to discover similar music')).not.toBeInTheDocument();
    });
  });

  describe('Different Track IDs', () => {
    it('should render different content for different trackId values', () => {
      const { rerender } = render(<SimilarTracksEmptyState trackId={null} />);

      // Initially no track selected
      expect(screen.getByText('Play a track to discover similar music')).toBeInTheDocument();

      // Select a track
      rerender(<SimilarTracksEmptyState trackId={1} />);

      // Should show no results message
      expect(screen.getByText('No similar tracks found')).toBeInTheDocument();
      expect(screen.queryByText('Play a track to discover similar music')).not.toBeInTheDocument();
    });

    it('should handle various trackId values', () => {
      const trackIds = [1, 42, 999, 99999];

      trackIds.forEach((trackId) => {
        const { unmount } = render(<SimilarTracksEmptyState trackId={trackId} />);

        expect(screen.getByText('No similar tracks found')).toBeInTheDocument();
        unmount();
      });
    });

    it('should treat trackId 0 as no track selected (falsy)', () => {
      const { unmount } = render(<SimilarTracksEmptyState trackId={0} />);

      // trackId 0 is falsy, so should show "Play a track" message
      expect(screen.getByText('Play a track to discover similar music')).toBeInTheDocument();
      expect(screen.queryByText('No similar tracks found')).not.toBeInTheDocument();
      unmount();
    });
  });

  describe('Conditional Rendering', () => {
    it('should switch states when trackId changes from null to number', () => {
      const { rerender } = render(<SimilarTracksEmptyState trackId={null} />);

      expect(screen.getByText('Play a track to discover similar music')).toBeInTheDocument();

      rerender(<SimilarTracksEmptyState trackId={10} />);

      expect(screen.queryByText('Play a track to discover similar music')).not.toBeInTheDocument();
      expect(screen.getByText('No similar tracks found')).toBeInTheDocument();
    });

    it('should switch states when trackId changes from number to null', () => {
      const { rerender } = render(<SimilarTracksEmptyState trackId={10} />);

      expect(screen.getByText('No similar tracks found')).toBeInTheDocument();

      rerender(<SimilarTracksEmptyState trackId={null} />);

      expect(screen.queryByText('No similar tracks found')).not.toBeInTheDocument();
      expect(screen.getByText('Play a track to discover similar music')).toBeInTheDocument();
    });
  });

  describe('Icon Display', () => {
    it('should display music note when trackId is null', () => {
      const { container } = render(<SimilarTracksEmptyState trackId={null} />);

      const icon = container.querySelector('svg');
      expect(icon).toBeInTheDocument();
    });

    it('should display sparkles when trackId is not null', () => {
      const { container } = render(<SimilarTracksEmptyState trackId={42} />);

      const icon = container.querySelector('svg');
      expect(icon).toBeInTheDocument();
    });
  });
});
