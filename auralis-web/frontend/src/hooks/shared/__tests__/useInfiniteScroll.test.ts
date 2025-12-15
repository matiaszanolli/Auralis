/**
 * Tests for useInfiniteScroll Hook
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Tests the infinite scroll functionality hook
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { act } from 'react-dom/test-utils';
import { useInfiniteScroll } from '../useInfiniteScroll';

// Mock IntersectionObserver with proper tracking
let mockInstances: any[] = [];
let currentCallback: IntersectionObserverCallback | null = null;

const mockIntersectionObserver = vi.fn((callback: IntersectionObserverCallback) => {
  // Store the current callback globally so we can trigger it from tests
  currentCallback = callback;

  const instance = {
    observe: vi.fn((element: Element) => {}),
    unobserve: vi.fn((element: Element) => {}),
    disconnect: vi.fn(() => {}),
  };

  mockInstances.push(instance);
  return instance;
});

// Helper to trigger intersection
const triggerIntersection = (isIntersecting: boolean, targetElement?: Element) => {
  if (!currentCallback) return;

  // Create a mock entry for the target element
  const mockEntry = {
    isIntersecting,
    target: targetElement || document.createElement('div'),
    boundingClientRect: {} as DOMRectReadOnly,
    intersectionRatio: isIntersecting ? 1 : 0,
    intersectionRect: {} as DOMRectReadOnly,
    rootBounds: null,
    time: Date.now(),
  } as IntersectionObserverEntry;

  currentCallback([mockEntry], {} as IntersectionObserver);
};

describe('useInfiniteScroll', () => {
  let consoleErrorSpy: any;

  beforeEach(() => {
    // Clear all mocks
    mockIntersectionObserver.mockClear();
    vi.clearAllMocks();

    // Reset global state
    mockInstances = [];
    currentCallback = null;

    // Setup IntersectionObserver mock
    global.IntersectionObserver = mockIntersectionObserver as any;

    // Mock console.error to suppress expected errors
    consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(async () => {
    await new Promise(resolve => setTimeout(resolve, 0)); // Flush microtasks
    vi.clearAllTimers();
    vi.useRealTimers();
    if (consoleErrorSpy) {
      consoleErrorSpy.mockRestore();
    }
    // Clean up global state
    mockInstances = [];
    currentCallback = null;
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

      const { result, rerender } = renderHook(
        ({ hasMore }) =>
          useInfiniteScroll({
            onLoadMore,
            hasMore,
            isLoading: false,
          }),
        { initialProps: { hasMore: false } }
      );

      // Set up a target element
      const targetElement = document.createElement('div');
      (result.current.observerTarget as any).current = targetElement;

      // Force effect to re-run by changing a hook prop
      rerender({ hasMore: true });

      // Wait for observer to be created
      await waitFor(() => {
        expect(mockInstances.length).toBeGreaterThan(0);
      });

      // Trigger intersection
      triggerIntersection(true, targetElement);

      await waitFor(() => {
        expect(onLoadMore).toHaveBeenCalledTimes(1);
      });
    });

    it('should not call onLoadMore when hasMore is false', async () => {
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
      (result.current.observerTarget as any).current = targetElement;

      // Force effect to re-run by changing hasMore
      rerender({ hasMore: false });

      await waitFor(() => {
        expect(mockInstances.length).toBeGreaterThan(0);
      });

      triggerIntersection(true, targetElement);

      await waitFor(() => {
        expect(onLoadMore).not.toHaveBeenCalled();
      }, { timeout: 100 });
    });

    it('should not call onLoadMore when isLoading is true', async () => {
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

      const targetElement = document.createElement('div');
      (result.current.observerTarget as any).current = targetElement;

      // Force effect to re-run by changing isLoading
      rerender({ isLoading: true });

      await waitFor(() => {
        expect(mockInstances.length).toBeGreaterThan(0);
      });

      triggerIntersection(true, targetElement);

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
    it('should use custom threshold', async () => {
      const onLoadMore = vi.fn().mockResolvedValue(undefined);

      const { result, rerender } = renderHook(
        ({ hasMore }) =>
          useInfiniteScroll({
            threshold: 0.5,
            onLoadMore,
            hasMore,
            isLoading: false,
          }),
        { initialProps: { hasMore: false } }
      );

      // Set target and rerender to trigger effect
      const targetElement = document.createElement('div');
      (result.current.observerTarget as any).current = targetElement;
      rerender({ hasMore: true });

      // Wait for observer to be created with custom threshold
      await waitFor(() => {
        expect(global.IntersectionObserver).toHaveBeenCalledWith(
          expect.any(Function),
          expect.objectContaining({ threshold: 0.5 })
        );
      });
    });

    it('should use default threshold of 0.8', async () => {
      const onLoadMore = vi.fn().mockResolvedValue(undefined);

      const { result, rerender } = renderHook(
        ({ hasMore }) =>
          useInfiniteScroll({
            onLoadMore,
            hasMore,
            isLoading: false,
          }),
        { initialProps: { hasMore: false } }
      );

      // Set target and rerender to trigger effect
      const targetElement = document.createElement('div');
      (result.current.observerTarget as any).current = targetElement;
      rerender({ hasMore: true });

      // Wait for observer to be created with default threshold
      await waitFor(() => {
        expect(global.IntersectionObserver).toHaveBeenCalledWith(
          expect.any(Function),
          expect.objectContaining({ threshold: 0.8 })
        );
      });
    });

    it('should use custom rootMargin', async () => {
      const onLoadMore = vi.fn().mockResolvedValue(undefined);

      const { result, rerender } = renderHook(
        ({ hasMore }) =>
          useInfiniteScroll({
            rootMargin: '200px',
            onLoadMore,
            hasMore,
            isLoading: false,
          }),
        { initialProps: { hasMore: false } }
      );

      // Set target and rerender to trigger effect
      const targetElement = document.createElement('div');
      (result.current.observerTarget as any).current = targetElement;
      rerender({ hasMore: true });

      // Wait for observer to be created with custom rootMargin
      await waitFor(() => {
        expect(global.IntersectionObserver).toHaveBeenCalledWith(
          expect.any(Function),
          expect.objectContaining({ rootMargin: '200px' })
        );
      });
    });

    it('should use default rootMargin of 100px', async () => {
      const onLoadMore = vi.fn().mockResolvedValue(undefined);

      const { result, rerender } = renderHook(
        ({ hasMore }) =>
          useInfiniteScroll({
            onLoadMore,
            hasMore,
            isLoading: false,
          }),
        { initialProps: { hasMore: false } }
      );

      // Set target and rerender to trigger effect
      const targetElement = document.createElement('div');
      (result.current.observerTarget as any).current = targetElement;
      rerender({ hasMore: true });

      // Wait for observer to be created with default rootMargin
      await waitFor(() => {
        expect(global.IntersectionObserver).toHaveBeenCalledWith(
          expect.any(Function),
          expect.objectContaining({ rootMargin: '100px' })
        );
      });
    });
  });

  describe('Loading state management', () => {
    it('should set isFetching to true while loading', async () => {
      let resolveLoad: () => void;
      const onLoadMore = vi.fn(() => new Promise<void>(resolve => {
        resolveLoad = resolve;
      }));

      const { result, rerender } = renderHook(
        ({ hasMore }) =>
          useInfiniteScroll({
            onLoadMore,
            hasMore,
            isLoading: false,
          }),
        { initialProps: { hasMore: false } }
      );

      const targetElement = document.createElement('div');
      (result.current.observerTarget as any).current = targetElement;

      // Force effect to re-run by changing hasMore
      rerender({ hasMore: true });

      await waitFor(() => {
        expect(mockInstances.length).toBeGreaterThan(0);
      });

      expect(result.current.isFetching).toBe(false);

      triggerIntersection(true, targetElement);

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
        new Promise(resolve => setTimeout(resolve, 50))
      );

      const { result, rerender } = renderHook(
        ({ hasMore }) =>
          useInfiniteScroll({
            onLoadMore,
            hasMore,
            isLoading: false,
          }),
        { initialProps: { hasMore: false } }
      );

      const targetElement = document.createElement('div');
      (result.current.observerTarget as any).current = targetElement;

      // Force effect to re-run by changing hasMore
      rerender({ hasMore: true });

      await waitFor(() => {
        expect(mockInstances.length).toBeGreaterThan(0);
      });

      // Trigger first intersection
      triggerIntersection(true, targetElement);

      // Wait for the first call to be made
      await waitFor(() => {
        expect(onLoadMore).toHaveBeenCalledTimes(1);
      });

      // Trigger more intersections while the first is still loading
      // These should NOT trigger additional onLoadMore calls
      triggerIntersection(true, targetElement);
      triggerIntersection(true, targetElement);

      // Verify still only 1 call even with multiple intersections
      await waitFor(
        () => {
          expect(onLoadMore).toHaveBeenCalledTimes(1);
        },
        { timeout: 100 }
      );
    });
  });

  describe('Error handling', () => {
    it('should handle onLoadMore errors gracefully', async () => {
      const onLoadMore = vi.fn().mockRejectedValue(new Error('Load failed'));

      const { result, rerender } = renderHook(
        ({ hasMore }) =>
          useInfiniteScroll({
            onLoadMore,
            hasMore,
            isLoading: false,
          }),
        { initialProps: { hasMore: false } }
      );

      const targetElement = document.createElement('div');
      (result.current.observerTarget as any).current = targetElement;

      // Force effect to re-run by changing hasMore
      rerender({ hasMore: true });

      // Wait for observer to be created
      await waitFor(() => {
        expect(mockInstances.length).toBeGreaterThan(0);
        expect(currentCallback).toBeDefined();
      });

      triggerIntersection(true, targetElement);

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

      const { result, rerender } = renderHook(
        ({ hasMore }) =>
          useInfiniteScroll({
            onLoadMore,
            hasMore,
            isLoading: false,
          }),
        { initialProps: { hasMore: false } }
      );

      const targetElement = document.createElement('div');
      (result.current.observerTarget as any).current = targetElement;

      // Force effect to re-run by changing hasMore
      rerender({ hasMore: true });

      // Wait for observer to be created
      await waitFor(() => {
        expect(mockInstances.length).toBeGreaterThan(0);
        expect(currentCallback).toBeDefined();
      });

      // First attempt (fails)
      triggerIntersection(true, targetElement);

      await waitFor(() => {
        expect(onLoadMore).toHaveBeenCalledTimes(1);
      });

      await waitFor(() => {
        expect(result.current.isFetching).toBe(false);
      });

      // Second attempt (succeeds)
      triggerIntersection(true, targetElement);

      await waitFor(() => {
        expect(onLoadMore).toHaveBeenCalledTimes(2);
      });
    });
  });

  describe('Observer lifecycle', () => {
    it('should create observer when target is set', async () => {
      const onLoadMore = vi.fn().mockResolvedValue(undefined);

      const { result, rerender } = renderHook(
        ({ hasMore }) =>
          useInfiniteScroll({
            onLoadMore,
            hasMore,
            isLoading: false,
          }),
        { initialProps: { hasMore: false } }
      );

      // Initially no observer since no target
      expect(mockInstances.length).toBe(0);

      // Set target
      const targetElement = document.createElement('div');
      (result.current.observerTarget as any).current = targetElement;

      // Force effect to re-run by changing a hook prop
      rerender({ hasMore: true });

      // Now observer should have been created
      await waitFor(() => {
        expect(mockInstances.length).toBeGreaterThan(0);
      });
    });

    it('should cleanup observer on unmount', async () => {
      const onLoadMore = vi.fn().mockResolvedValue(undefined);

      const { result, rerender, unmount } = renderHook(
        ({ hasMore }) =>
          useInfiniteScroll({
            onLoadMore,
            hasMore,
            isLoading: false,
          }),
        { initialProps: { hasMore: false } }
      );

      const targetElement = document.createElement('div');
      (result.current.observerTarget as any).current = targetElement;

      // Force effect to re-run
      rerender({ hasMore: true });

      // Wait for observer to be created
      await waitFor(() => {
        expect(mockInstances.length).toBeGreaterThan(0);
      });

      // Get the last created mock instance
      const lastInstance = mockInstances[mockInstances.length - 1];
      expect(lastInstance).toBeDefined();

      // Unmount should call unobserve
      act(() => {
        unmount();
      });

      expect(lastInstance.unobserve).toHaveBeenCalledWith(targetElement);
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
        { initialProps: { hasMore: false } }
      );

      const targetElement = document.createElement('div');
      (result.current.observerTarget as any).current = targetElement;

      // Change hasMore to true to trigger effect
      rerender({ hasMore: true });

      // Wait for observer to be created
      await waitFor(() => {
        expect(mockInstances.length).toBeGreaterThan(0);
        expect(currentCallback).toBeDefined();
      });

      // Should load when hasMore is true
      triggerIntersection(true, targetElement);

      await waitFor(() => {
        expect(onLoadMore).toHaveBeenCalledTimes(1);
      });

      // Change hasMore to false - this recreates the observer
      rerender({ hasMore: false });

      // Should not load when hasMore is false
      triggerIntersection(true, targetElement);

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
      triggerIntersection(true);

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
      (result.current.observerTarget as any).current = targetElement;

      // Trigger non-intersection
      triggerIntersection(false);

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
      (result.current.observerTarget as any).current = targetElement;

      // Rapid toggles
      rerender({ hasMore: false });
      rerender({ hasMore: true });
      rerender({ hasMore: false });
      rerender({ hasMore: true });

      triggerIntersection(true);

      // Should eventually load when hasMore is true
      await waitFor(() => {
        expect(onLoadMore).toHaveBeenCalled();
      });
    });
  });
});
