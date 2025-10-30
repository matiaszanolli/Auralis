/**
 * Tests for useInfiniteScroll Hook
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Tests the infinite scroll functionality hook
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { useInfiniteScroll } from '../useInfiniteScroll';

// Mock IntersectionObserver
let observerCallback: IntersectionObserverCallback | null = null;
let observedElements: Set<Element> = new Set();

const mockIntersectionObserver = vi.fn((callback: IntersectionObserverCallback) => {
  observerCallback = callback;
  return {
    observe: (element: Element) => {
      observedElements.add(element);
    },
    unobserve: (element: Element) => {
      observedElements.delete(element);
    },
    disconnect: () => {
      observedElements.clear();
    },
  };
});

// Helper to trigger intersection
const triggerIntersection = (isIntersecting: boolean) => {
  if (!observerCallback) return;

  const entries: IntersectionObserverEntry[] = Array.from(observedElements).map(target => ({
    isIntersecting,
    target,
    boundingClientRect: {} as DOMRectReadOnly,
    intersectionRatio: isIntersecting ? 1 : 0,
    intersectionRect: {} as DOMRectReadOnly,
    rootBounds: null,
    time: Date.now(),
  }));

  observerCallback(entries, {} as IntersectionObserver);
};

describe('useInfiniteScroll', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    observerCallback = null;
    observedElements.clear();

    // Setup IntersectionObserver mock
    global.IntersectionObserver = mockIntersectionObserver as any;

    // Mock console.error to suppress expected errors
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  describe('Basic functionality', () => {
    it('should return observerTarget ref and isFetching state', () => {
      const onLoadMore = vi.fn().mockResolvedValue(undefined);

      const { result } = renderHook(() =>
        useInfiniteScroll({
          onLoadMore,
          hasMore: true,
          isLoading: false,
        })
      );

      expect(result.current.observerTarget).toBeDefined();
      expect(result.current.observerTarget.current).toBeNull();
      expect(result.current.isFetching).toBe(false);
    });

    it('should call onLoadMore when target intersects', async () => {
      const onLoadMore = vi.fn().mockResolvedValue(undefined);

      const { result, rerender } = renderHook(() =>
        useInfiniteScroll({
          onLoadMore,
          hasMore: true,
          isLoading: false,
        })
      );

      // Set up a target element
      const targetElement = document.createElement('div');
      result.current.observerTarget.current = targetElement;

      // Force re-render to trigger useEffect
      rerender();

      // Trigger intersection
      triggerIntersection(true);

      await waitFor(() => {
        expect(onLoadMore).toHaveBeenCalledTimes(1);
      });
    });

    it('should not call onLoadMore when hasMore is false', async () => {
      const onLoadMore = vi.fn().mockResolvedValue(undefined);

      const { result } = renderHook(() =>
        useInfiniteScroll({
          onLoadMore,
          hasMore: false,
          isLoading: false,
        })
      );

      const targetElement = document.createElement('div');
      result.current.observerTarget.current = targetElement;

      mockObserver.triggerIntersection(true);

      await waitFor(() => {
        expect(onLoadMore).not.toHaveBeenCalled();
      }, { timeout: 100 });
    });

    it('should not call onLoadMore when isLoading is true', async () => {
      const onLoadMore = vi.fn().mockResolvedValue(undefined);

      const { result } = renderHook(() =>
        useInfiniteScroll({
          onLoadMore,
          hasMore: true,
          isLoading: true,
        })
      );

      const targetElement = document.createElement('div');
      result.current.observerTarget.current = targetElement;

      mockObserver.triggerIntersection(true);

      await waitFor(() => {
        expect(onLoadMore).not.toHaveBeenCalled();
      }, { timeout: 100 });
    });

    it('should reflect isLoading in isFetching', () => {
      const onLoadMore = vi.fn().mockResolvedValue(undefined);

      const { result } = renderHook(() =>
        useInfiniteScroll({
          onLoadMore,
          hasMore: true,
          isLoading: true,
        })
      );

      expect(result.current.isFetching).toBe(true);
    });
  });

  describe('Options', () => {
    it('should use custom threshold', () => {
      const onLoadMore = vi.fn().mockResolvedValue(undefined);

      renderHook(() =>
        useInfiniteScroll({
          threshold: 0.5,
          onLoadMore,
          hasMore: true,
          isLoading: false,
        })
      );

      expect(global.IntersectionObserver).toHaveBeenCalledWith(
        expect.any(Function),
        expect.objectContaining({ threshold: 0.5 })
      );
    });

    it('should use default threshold of 0.8', () => {
      const onLoadMore = vi.fn().mockResolvedValue(undefined);

      renderHook(() =>
        useInfiniteScroll({
          onLoadMore,
          hasMore: true,
          isLoading: false,
        })
      );

      expect(global.IntersectionObserver).toHaveBeenCalledWith(
        expect.any(Function),
        expect.objectContaining({ threshold: 0.8 })
      );
    });

    it('should use custom rootMargin', () => {
      const onLoadMore = vi.fn().mockResolvedValue(undefined);

      renderHook(() =>
        useInfiniteScroll({
          rootMargin: '200px',
          onLoadMore,
          hasMore: true,
          isLoading: false,
        })
      );

      expect(global.IntersectionObserver).toHaveBeenCalledWith(
        expect.any(Function),
        expect.objectContaining({ rootMargin: '200px' })
      );
    });

    it('should use default rootMargin of 100px', () => {
      const onLoadMore = vi.fn().mockResolvedValue(undefined);

      renderHook(() =>
        useInfiniteScroll({
          onLoadMore,
          hasMore: true,
          isLoading: false,
        })
      );

      expect(global.IntersectionObserver).toHaveBeenCalledWith(
        expect.any(Function),
        expect.objectContaining({ rootMargin: '100px' })
      );
    });
  });

  describe('Loading state management', () => {
    it('should set isFetching to true while loading', async () => {
      let resolveLoad: () => void;
      const onLoadMore = vi.fn(() => new Promise<void>(resolve => {
        resolveLoad = resolve;
      }));

      const { result } = renderHook(() =>
        useInfiniteScroll({
          onLoadMore,
          hasMore: true,
          isLoading: false,
        })
      );

      const targetElement = document.createElement('div');
      result.current.observerTarget.current = targetElement;

      expect(result.current.isFetching).toBe(false);

      mockObserver.triggerIntersection(true);

      await waitFor(() => {
        expect(result.current.isFetching).toBe(true);
      });

      resolveLoad!();

      await waitFor(() => {
        expect(result.current.isFetching).toBe(false);
      });
    });

    it('should not trigger multiple loads simultaneously', async () => {
      const onLoadMore = vi.fn().mockImplementation(() =>
        new Promise(resolve => setTimeout(resolve, 100))
      );

      const { result } = renderHook(() =>
        useInfiniteScroll({
          onLoadMore,
          hasMore: true,
          isLoading: false,
        })
      );

      const targetElement = document.createElement('div');
      result.current.observerTarget.current = targetElement;

      // Trigger multiple intersections rapidly
      mockObserver.triggerIntersection(true);
      mockObserver.triggerIntersection(true);
      mockObserver.triggerIntersection(true);

      await waitFor(() => {
        expect(onLoadMore).toHaveBeenCalledTimes(1);
      });
    });
  });

  describe('Error handling', () => {
    it('should handle onLoadMore errors gracefully', async () => {
      const onLoadMore = vi.fn().mockRejectedValue(new Error('Load failed'));

      const { result } = renderHook(() =>
        useInfiniteScroll({
          onLoadMore,
          hasMore: true,
          isLoading: false,
        })
      );

      const targetElement = document.createElement('div');
      result.current.observerTarget.current = targetElement;

      mockObserver.triggerIntersection(true);

      await waitFor(() => {
        expect(console.error).toHaveBeenCalledWith(
          'Error loading more items:',
          expect.any(Error)
        );
      });

      // Should set isFetching back to false after error
      await waitFor(() => {
        expect(result.current.isFetching).toBe(false);
      });
    });

    it('should allow retry after error', async () => {
      let callCount = 0;
      const onLoadMore = vi.fn().mockImplementation(() => {
        callCount++;
        if (callCount === 1) {
          return Promise.reject(new Error('First call fails'));
        }
        return Promise.resolve();
      });

      const { result } = renderHook(() =>
        useInfiniteScroll({
          onLoadMore,
          hasMore: true,
          isLoading: false,
        })
      );

      const targetElement = document.createElement('div');
      result.current.observerTarget.current = targetElement;

      // First attempt (fails)
      mockObserver.triggerIntersection(true);

      await waitFor(() => {
        expect(onLoadMore).toHaveBeenCalledTimes(1);
      });

      await waitFor(() => {
        expect(result.current.isFetching).toBe(false);
      });

      // Second attempt (succeeds)
      mockObserver.triggerIntersection(true);

      await waitFor(() => {
        expect(onLoadMore).toHaveBeenCalledTimes(2);
      });
    });
  });

  describe('Observer lifecycle', () => {
    it('should create observer when target is set', () => {
      const onLoadMore = vi.fn().mockResolvedValue(undefined);

      const { result } = renderHook(() =>
        useInfiniteScroll({
          onLoadMore,
          hasMore: true,
          isLoading: false,
        })
      );

      expect(global.IntersectionObserver).toHaveBeenCalled();

      const targetElement = document.createElement('div');
      result.current.observerTarget.current = targetElement;
    });

    it('should cleanup observer on unmount', () => {
      const onLoadMore = vi.fn().mockResolvedValue(undefined);
      const unobserveSpy = vi.fn();

      mockObserver.unobserve = unobserveSpy;

      const { result, unmount } = renderHook(() =>
        useInfiniteScroll({
          onLoadMore,
          hasMore: true,
          isLoading: false,
        })
      );

      const targetElement = document.createElement('div');
      result.current.observerTarget.current = targetElement;

      unmount();

      expect(unobserveSpy).toHaveBeenCalledWith(targetElement);
    });
  });

  describe('Dynamic prop updates', () => {
    it('should respond to hasMore changes', async () => {
      const onLoadMore = vi.fn().mockResolvedValue(undefined);

      const { result, rerender } = renderHook(
        ({ hasMore }) =>
          useInfiniteScroll({
            onLoadMore,
            hasMore,
            isLoading: false,
          }),
        { initialProps: { hasMore: true } }
      );

      const targetElement = document.createElement('div');
      result.current.observerTarget.current = targetElement;

      // Should load when hasMore is true
      mockObserver.triggerIntersection(true);

      await waitFor(() => {
        expect(onLoadMore).toHaveBeenCalledTimes(1);
      });

      // Change hasMore to false
      rerender({ hasMore: false });

      // Should not load when hasMore is false
      mockObserver.triggerIntersection(true);

      await waitFor(() => {
        expect(onLoadMore).toHaveBeenCalledTimes(1); // Still 1
      }, { timeout: 100 });
    });

    it('should respond to isLoading changes', () => {
      const onLoadMore = vi.fn().mockResolvedValue(undefined);

      const { result, rerender } = renderHook(
        ({ isLoading }) =>
          useInfiniteScroll({
            onLoadMore,
            hasMore: true,
            isLoading,
          }),
        { initialProps: { isLoading: false } }
      );

      expect(result.current.isFetching).toBe(false);

      rerender({ isLoading: true });

      expect(result.current.isFetching).toBe(true);
    });
  });

  describe('Edge cases', () => {
    it('should handle null target gracefully', () => {
      const onLoadMore = vi.fn().mockResolvedValue(undefined);

      const { result } = renderHook(() =>
        useInfiniteScroll({
          onLoadMore,
          hasMore: true,
          isLoading: false,
        })
      );

      // Don't set target element
      expect(result.current.observerTarget.current).toBeNull();

      // Should not crash or call onLoadMore
      mockObserver.triggerIntersection(true);

      expect(onLoadMore).not.toHaveBeenCalled();
    });

    it('should handle non-intersecting entries', async () => {
      const onLoadMore = vi.fn().mockResolvedValue(undefined);

      const { result } = renderHook(() =>
        useInfiniteScroll({
          onLoadMore,
          hasMore: true,
          isLoading: false,
        })
      );

      const targetElement = document.createElement('div');
      result.current.observerTarget.current = targetElement;

      // Trigger non-intersection
      mockObserver.triggerIntersection(false);

      await waitFor(() => {
        expect(onLoadMore).not.toHaveBeenCalled();
      }, { timeout: 100 });
    });

    it('should handle rapid hasMore toggles', async () => {
      const onLoadMore = vi.fn().mockResolvedValue(undefined);

      const { result, rerender } = renderHook(
        ({ hasMore }) =>
          useInfiniteScroll({
            onLoadMore,
            hasMore,
            isLoading: false,
          }),
        { initialProps: { hasMore: true } }
      );

      const targetElement = document.createElement('div');
      result.current.observerTarget.current = targetElement;

      // Rapid toggles
      rerender({ hasMore: false });
      rerender({ hasMore: true });
      rerender({ hasMore: false });
      rerender({ hasMore: true });

      mockObserver.triggerIntersection(true);

      // Should eventually load when hasMore is true
      await waitFor(() => {
        expect(onLoadMore).toHaveBeenCalled();
      });
    });
  });
});
