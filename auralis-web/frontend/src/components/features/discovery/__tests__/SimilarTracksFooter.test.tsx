/**
 * SimilarTracksFooter Component Tests
 *
 * Tests for footer with usage information:
 * - Mode display (fast lookup vs real-time search)
 * - Track count display
 * - Dynamic text based on props
 */

import { render, screen } from '@/test/test-utils';
import { SimilarTracksFooter } from '../SimilarTracksFooter';

describe('SimilarTracksFooter', () => {
  describe('Mode Display', () => {
    it('should display "fast lookup" when useGraph is true', () => {
      render(
        <SimilarTracksFooter useGraph={true} tracksCount={10} />
      );

      expect(screen.getByText(/⚡ Fast lookup/)).toBeInTheDocument();
    });

    it('should display "real-time search" when useGraph is false', () => {
      render(
        <SimilarTracksFooter useGraph={false} tracksCount={10} />
      );

      expect(screen.getByText(/🔍 Real-time search/)).toBeInTheDocument();
    });
  });

  describe('Track Count Display', () => {
    it('should display track count', () => {
      render(
        <SimilarTracksFooter useGraph={true} tracksCount={10} />
      );

      expect(screen.getByText(/10 tracks/)).toBeInTheDocument();
    });

    it('should handle zero tracks', () => {
      render(
        <SimilarTracksFooter useGraph={true} tracksCount={0} />
      );

      expect(screen.getByText(/0 tracks/)).toBeInTheDocument();
    });

    it('should handle various track counts', () => {
      const counts = [1, 5, 10, 25, 50, 100];

      counts.forEach((count) => {
        const { unmount } = render(
          <SimilarTracksFooter useGraph={true} tracksCount={count} />
        );

        expect(screen.getByText(new RegExp(`${count} tracks`))).toBeInTheDocument();
        unmount();
      });
    });

    it('should handle large track counts', () => {
      render(
        <SimilarTracksFooter useGraph={true} tracksCount={9999} />
      );

      expect(screen.getByText(/9999 tracks/)).toBeInTheDocument();
    });
  });

  describe('Mode and Count Combination', () => {
    it('should display both mode and count together', () => {
      render(
        <SimilarTracksFooter useGraph={true} tracksCount={42} />
      );

      const text = screen.getByText(/⚡ Fast lookup/);
      expect(text.textContent).toContain('42 tracks');
    });

    it('should toggle mode while keeping count', () => {
      const { rerender } = render(
        <SimilarTracksFooter useGraph={true} tracksCount={15} />
      );

      expect(screen.getByText(/⚡ Fast lookup/)).toBeInTheDocument();
      expect(screen.getByText(/15 tracks/)).toBeInTheDocument();

      rerender(
        <SimilarTracksFooter useGraph={false} tracksCount={15} />
      );

      expect(screen.queryByText(/⚡ Fast lookup/)).not.toBeInTheDocument();
      expect(screen.getByText(/🔍 Real-time search/)).toBeInTheDocument();
      expect(screen.getByText(/15 tracks/)).toBeInTheDocument();
    });

    it('should update count while keeping mode', () => {
      const { rerender } = render(
        <SimilarTracksFooter useGraph={true} tracksCount={10} />
      );

      expect(screen.getByText(/⚡ Fast lookup/)).toBeInTheDocument();
      expect(screen.getByText(/10 tracks/)).toBeInTheDocument();

      rerender(
        <SimilarTracksFooter useGraph={true} tracksCount={25} />
      );

      expect(screen.getByText(/⚡ Fast lookup/)).toBeInTheDocument();
      expect(screen.getByText(/25 tracks/)).toBeInTheDocument();
    });
  });

  describe('Props Integration', () => {
    it('should update when both props change', () => {
      const { rerender } = render(
        <SimilarTracksFooter useGraph={true} tracksCount={10} />
      );

      expect(screen.getByText(/⚡ Fast lookup.*10 tracks/)).toBeInTheDocument();

      rerender(
        <SimilarTracksFooter useGraph={false} tracksCount={30} />
      );

      expect(screen.getByText(/🔍 Real-time search.*30 tracks/)).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('should have readable text', () => {
      render(
        <SimilarTracksFooter useGraph={true} tracksCount={10} />
      );

      const text = screen.getByText(/⚡ Fast lookup/);
      expect(text).toBeInTheDocument();
      expect(text).toHaveTextContent('10 tracks');
    });

    it('should render footer properly', () => {
      const { container } = render(
        <SimilarTracksFooter useGraph={true} tracksCount={10} />
      );

      const box = container.querySelector('[class*="MuiBox"]');
      expect(box).toBeInTheDocument();
    });
  });

  describe('Edge Cases', () => {
    it('should handle both modes with single track', () => {
      const { rerender } = render(
        <SimilarTracksFooter useGraph={true} tracksCount={1} />
      );

      expect(screen.getByText(/1 tracks/)).toBeInTheDocument();

      rerender(
        <SimilarTracksFooter useGraph={false} tracksCount={1} />
      );

      expect(screen.getByText(/1 tracks/)).toBeInTheDocument();
    });

    it('should handle very large track counts', () => {
      render(
        <SimilarTracksFooter useGraph={true} tracksCount={1000000} />
      );

      expect(screen.getByText(/1000000 tracks/)).toBeInTheDocument();
    });
  });
});
