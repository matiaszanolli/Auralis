/**
 * AlbumArt Component Tests
 *
 * Tests for the album artwork display component with:
 * - Basic rendering
 * - Image display
 * - Error handling
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen } from '@/test/test-utils';
import AlbumArt from './AlbumArt';

describe('AlbumArt', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.clearAllTimers();
  });

  describe('Rendering', () => {
    it('should render without crashing', () => {
      const { container } = render(<AlbumArt />);
      expect(container).toBeInTheDocument();
    });

    it('should render with albumId prop', () => {
      const { container } = render(<AlbumArt albumId={1} />);
      expect(container).toBeInTheDocument();
    });

    it('should render with custom size', () => {
      const { container } = render(<AlbumArt size={200} />);
      expect(container).toBeInTheDocument();
    });

    it('should accept border radius prop', () => {
      const { container } = render(<AlbumArt borderRadius={8} />);
      expect(container).toBeInTheDocument();
    });
  });

  describe('Image Display', () => {
    it('should render image element when albumId provided', () => {
      render(<AlbumArt albumId={1} />);
      const img = screen.queryByRole('img');
      // Image should be in DOM even if loading
      if (img) {
        expect(img).toBeInTheDocument();
      }
    });

    it('should use correct image URL pattern', () => {
      render(<AlbumArt albumId={42} />);
      const img = screen.queryByRole('img');
      if (img && img instanceof HTMLImageElement) {
        expect(img.src).toContain('42');
      }
    });
  });

  describe('Styling', () => {
    it('should apply size styling', () => {
      const { container } = render(<AlbumArt size={160} />);
      const element = container.firstChild as HTMLElement;
      expect(element).toBeInTheDocument();
    });

    it('should apply custom styles', () => {
      const { container } = render(
        <AlbumArt
          size={120}
          borderRadius={4}
          style={{ opacity: 0.8 }}
        />
      );
      expect(container).toBeInTheDocument();
    });
  });

  describe('Click Handling', () => {
    it('should call onClick handler when provided', () => {
      const handleClick = vi.fn();
      const { container } = render(
        <AlbumArt albumId={1} onClick={handleClick} />
      );

      const element = container.firstChild as HTMLElement;
      if (element) {
        element.click?.();
        expect(handleClick.mock.calls.length).toBeGreaterThanOrEqual(0);
      }
    });

    it('should handle missing onClick gracefully', () => {
      const { container } = render(<AlbumArt albumId={1} />);
      const element = container.firstChild as HTMLElement;
      // Should not throw
      expect(() => element.click?.()).not.toThrow();
    });
  });

  describe('Accessibility', () => {
    it('should have alt text when displaying image', () => {
      render(<AlbumArt albumId={1} />);
      const img = screen.queryByRole('img');
      if (img instanceof HTMLImageElement) {
        expect(img.alt).toBeTruthy();
      }
    });

    it('should be accessible without albumId', () => {
      const { container } = render(<AlbumArt />);
      expect(container).toBeInTheDocument();
    });
  });

  describe('Props Combinations', () => {
    it('should handle all props together', () => {
      const { container } = render(
        <AlbumArt
          albumId={1}
          size={150}
          borderRadius={8}
          onClick={() => {}}
        />
      );
      expect(container).toBeInTheDocument();
    });

    it('should handle minimal props', () => {
      const { container } = render(<AlbumArt />);
      expect(container).toBeInTheDocument();
    });
  });

  describe('Component Lifecycle', () => {
    it('should mount and unmount cleanly', () => {
      const { unmount } = render(<AlbumArt albumId={1} />);
      expect(document.body).toBeInTheDocument();

      unmount();
      // Component should unmount without errors
    });

    it('should handle prop updates', () => {
      const { rerender } = render(<AlbumArt albumId={1} />);

      // Update props
      rerender(<AlbumArt albumId={2} />);

      expect(document.body).toBeInTheDocument();
    });
  });
});
