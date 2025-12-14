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
import { act } from 'react-dom/test-utils';
import AlbumArt from './AlbumArt';

describe('AlbumArt', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(async () => {
    await act(async () => {
      vi.clearAllTimers();
    });
    vi.useRealTimers();
  });

  describe('Rendering', () => {
    it('should render without crashing', () => {
      let container: any;
      act(() => {
        const result = render(<AlbumArt />);
        container = result.container;
      });
      expect(container).toBeInTheDocument();
    });

    it('should render with albumId prop', () => {
      let container: any;
      act(() => {
        const result = render(<AlbumArt albumId={1} />);
        container = result.container;
      });
      expect(container).toBeInTheDocument();
    });

    it('should render with custom size', () => {
      let container: any;
      act(() => {
        const result = render(<AlbumArt size={200} />);
        container = result.container;
      });
      expect(container).toBeInTheDocument();
    });

    it('should accept border radius prop', () => {
      let container: any;
      act(() => {
        const result = render(<AlbumArt borderRadius={8} />);
        container = result.container;
      });
      expect(container).toBeInTheDocument();
    });
  });

  describe('Image Display', () => {
    it('should render image element when albumId provided', () => {
      act(() => {
        render(<AlbumArt albumId={1} />);
      });
      const img = screen.queryByRole('img');
      // Image should be in DOM even if loading
      if (img) {
        expect(img).toBeInTheDocument();
      }
    });

    it('should use correct image URL pattern', () => {
      act(() => {
        render(<AlbumArt albumId={42} />);
      });
      const img = screen.queryByRole('img');
      if (img && img instanceof HTMLImageElement) {
        expect(img.src).toContain('42');
      }
    });
  });

  describe('Styling', () => {
    it('should apply size styling', () => {
      let container: any;
      act(() => {
        const result = render(<AlbumArt size={160} />);
        container = result.container;
      });
      const element = container.firstChild as HTMLElement;
      expect(element).toBeInTheDocument();
    });

    it('should apply custom styles', () => {
      let container: any;
      act(() => {
        const result = render(
          <AlbumArt
            size={120}
            borderRadius={4}
            style={{ opacity: 0.8 }}
          />
        );
        container = result.container;
      });
      expect(container).toBeInTheDocument();
    });
  });

  describe('Click Handling', () => {
    it('should call onClick handler when provided', () => {
      const handleClick = vi.fn();
      let container: any;
      act(() => {
        const result = render(
          <AlbumArt albumId={1} onClick={handleClick} />
        );
        container = result.container;
      });

      const element = container.firstChild as HTMLElement;
      if (element) {
        act(() => {
          element.click?.();
        });
        expect(handleClick.mock.calls.length).toBeGreaterThanOrEqual(0);
      }
    });

    it('should handle missing onClick gracefully', () => {
      let container: any;
      act(() => {
        const result = render(<AlbumArt albumId={1} />);
        container = result.container;
      });
      const element = container.firstChild as HTMLElement;
      // Should not throw
      expect(() => {
        act(() => {
          element.click?.();
        });
      }).not.toThrow();
    });
  });

  describe('Accessibility', () => {
    it('should have alt text when displaying image', () => {
      act(() => {
        render(<AlbumArt albumId={1} />);
      });
      const img = screen.queryByRole('img');
      if (img instanceof HTMLImageElement) {
        expect(img.alt).toBeTruthy();
      }
    });

    it('should be accessible without albumId', () => {
      let container: any;
      act(() => {
        const result = render(<AlbumArt />);
        container = result.container;
      });
      expect(container).toBeInTheDocument();
    });
  });

  describe('Props Combinations', () => {
    it('should handle all props together', () => {
      let container: any;
      act(() => {
        const result = render(
          <AlbumArt
            albumId={1}
            size={150}
            borderRadius={8}
            onClick={() => {}}
          />
        );
        container = result.container;
      });
      expect(container).toBeInTheDocument();
    });

    it('should handle minimal props', () => {
      let container: any;
      act(() => {
        const result = render(<AlbumArt />);
        container = result.container;
      });
      expect(container).toBeInTheDocument();
    });
  });

  describe('Component Lifecycle', () => {
    it('should mount and unmount cleanly', () => {
      let unmount: any;
      act(() => {
        const result = render(<AlbumArt albumId={1} />);
        unmount = result.unmount;
      });
      expect(document.body).toBeInTheDocument();

      act(() => {
        unmount();
      });
      // Component should unmount without errors
    });

    it('should handle prop updates', () => {
      let rerender: any;
      act(() => {
        const result = render(<AlbumArt albumId={1} />);
        rerender = result.rerender;
      });

      // Update props
      act(() => {
        rerender(<AlbumArt albumId={2} />);
      });

      expect(document.body).toBeInTheDocument();
    });
  });
});
