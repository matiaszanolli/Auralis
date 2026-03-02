/**
 * GlobalSearch Component Tests
 *
 * Simplified test suite focusing on core functionality:
 * - Rendering the search input
 * - Basic input interaction
 * - Component initialization
 */

import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import { render, screen } from '@/test/test-utils';
import userEvent from '@testing-library/user-event';
import { act } from 'react-dom/test-utils';
import GlobalSearch from '../Search/GlobalSearch';

// Mock AlbumArt component to avoid image loading issues
vi.mock('../../album/AlbumArt', () => ({
  default: function MockAlbumArt({ albumId, size }: any) {
    return (
      <div data-testid={`album-art-${albumId}`} style={{ width: size, height: size }}>
        Album {albumId}
      </div>
    );
  },
}));

describe('GlobalSearch', () => {
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
    it('should render search input field', () => {
      act(() => {
        render(<GlobalSearch />);
      });

      const input = screen.getByPlaceholderText(/search/i);
      expect(input).toBeInTheDocument();
    });

    it('should have input type text', () => {
      act(() => {
        render(<GlobalSearch />);
      });

      const input = screen.getByPlaceholderText(/search/i) as HTMLInputElement;
      expect(input.type).toBe('text');
    });

    it('should render without crashing', () => {
      let container: any;
      act(() => {
        const result = render(<GlobalSearch />);
        container = result.container;
      });
      expect(container).toBeInTheDocument();
    });
  });

  describe('Input Interaction', () => {
    it('should update input value on type', async () => {
      const user = userEvent.setup();
      await act(async () => {
        render(<GlobalSearch />);
      });

      const input = screen.getByPlaceholderText(/search/i) as HTMLInputElement;

      await act(async () => {
        await user.type(input, 'Queen');
      });

      expect(input.value).toBe('Queen');
    });

    it('should handle text input with special characters', async () => {
      const user = userEvent.setup();
      await act(async () => {
        render(<GlobalSearch />);
      });

      const input = screen.getByPlaceholderText(/search/i) as HTMLInputElement;

      await act(async () => {
        await user.type(input, 'Test & Special');
      });

      expect(input.value).toContain('Test');
      expect(input.value).toContain('Special');
    });

    it('should clear input value', async () => {
      const user = userEvent.setup();
      await act(async () => {
        render(<GlobalSearch />);
      });

      const input = screen.getByPlaceholderText(/search/i) as HTMLInputElement;

      await act(async () => {
        await user.type(input, 'test');
      });

      expect(input.value).toBe('test');

      await act(async () => {
        await user.clear(input);
      });

      expect(input.value).toBe('');
    });
  });

  describe('Accessibility', () => {
    it('should have proper input attributes', () => {
      act(() => {
        render(<GlobalSearch />);
      });

      const input = screen.getByPlaceholderText(/search/i);
      expect(input).toHaveAttribute('type', 'text');
    });

    it('should support keyboard navigation', async () => {
      await act(async () => {
        render(<GlobalSearch />);
      });

      const input = screen.getByPlaceholderText(/search/i);

      // Input should be focusable
      await act(async () => {
        input.focus();
      });

      expect(document.activeElement).toBe(input);
    });
  });

  describe('Edge Cases', () => {
    it('should handle long input text', async () => {
      const user = userEvent.setup();
      await act(async () => {
        render(<GlobalSearch />);
      });

      const input = screen.getByPlaceholderText(/search/i) as HTMLInputElement;
      const longText = 'A'.repeat(200);

      await act(async () => {
        await user.type(input, longText);
      });

      expect(input.value.length).toBe(200);
    });

    it('should handle rapid typing', async () => {
      const user = userEvent.setup();
      await act(async () => {
        render(<GlobalSearch />);
      });

      const input = screen.getByPlaceholderText(/search/i) as HTMLInputElement;

      await act(async () => {
        await user.type(input, 'Queens');
      });

      expect(input.value).toBe('Queens');
    });

    it('should handle unicode input', async () => {
      const user = userEvent.setup();
      await act(async () => {
        render(<GlobalSearch />);
      });

      const input = screen.getByPlaceholderText(/search/i) as HTMLInputElement;

      await act(async () => {
        await user.type(input, '音楽');
      });

      expect(input.value).toBe('音楽');
    });
  });

  describe('Component Lifecycle', () => {
    it('should mount and unmount without errors', () => {
      let unmount: any;
      act(() => {
        const result = render(<GlobalSearch />);
        unmount = result.unmount;
      });

      expect(screen.getByPlaceholderText(/search/i)).toBeInTheDocument();

      act(() => {
        unmount();
      });

      // Component should be removed
      expect(screen.queryByPlaceholderText(/search/i)).not.toBeInTheDocument();
    });

    it('should handle remounting', () => {
      let unmount: any;
      act(() => {
        const result = render(<GlobalSearch />);
        unmount = result.unmount;
      });
      expect(screen.getByPlaceholderText(/search/i)).toBeInTheDocument();

      unmount();

      // Remount
      act(() => {
        render(<GlobalSearch />);
      });
      expect(screen.getByPlaceholderText(/search/i)).toBeInTheDocument();
    });
  });
});
