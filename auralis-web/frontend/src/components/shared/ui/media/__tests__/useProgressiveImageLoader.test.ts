import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useProgressiveImageLoader } from '../useProgressiveImageLoader';

describe('useProgressiveImageLoader', () => {
  const imageSources: string[] = [];
  const imageInstances: MockImage[] = [];

  class MockImage {
    onload: (() => void) | null = null;
    onerror: (() => void) | null = null;
    private currentSrc = '';

    constructor() {
      imageInstances.push(this);
    }

    set src(value: string) {
      this.currentSrc = value;
      imageSources.push(value);
    }

    get src(): string {
      return this.currentSrc;
    }
  }

  beforeEach(() => {
    imageSources.length = 0;
    imageInstances.length = 0;
    vi.useFakeTimers();
    vi.stubGlobal('Image', MockImage as unknown as typeof Image);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it('appends retry with & when the source already has query parameters (#4866)', () => {
    renderHook(() => useProgressiveImageLoader({
      src: '/api/albums/1/artwork?size=64',
      maxRetries: 1,
    }));

    act(() => {
      imageInstances[0]?.onerror?.();
      vi.advanceTimersByTime(1000);
    });

    expect(imageSources).toContain('/api/albums/1/artwork?size=64&retry=1');
    expect(imageSources).not.toContain('/api/albums/1/artwork?size=64?retry=1');
  });

  describe('retry sequence (#5353)', () => {
    const failLatest = () => act(() => { imageInstances[imageInstances.length - 1]?.onerror?.(); });

    it('retries maxRetries times with exponential backoff, then reports the error once', () => {
      const onError = vi.fn();
      const { result } = renderHook(() => useProgressiveImageLoader({ src: '/a.jpg', maxRetries: 2, onError }));

      failLatest();                                  // initial load fails
      expect(imageInstances).toHaveLength(1);
      act(() => { vi.advanceTimersByTime(999); });
      expect(imageInstances).toHaveLength(1);        // first backoff is 1000 ms
      act(() => { vi.advanceTimersByTime(1); });
      expect(imageInstances).toHaveLength(2);

      failLatest();
      act(() => { vi.advanceTimersByTime(1999); });
      expect(imageInstances).toHaveLength(2);        // second backoff is 2000 ms
      act(() => { vi.advanceTimersByTime(1); });
      expect(imageInstances).toHaveLength(3);

      failLatest();                                  // third failure: budget spent
      act(() => { vi.advanceTimersByTime(60_000); });

      expect(imageInstances).toHaveLength(3);        // no endless retrying
      expect(imageSources).toEqual(['/a.jpg', '/a.jpg?retry=1', '/a.jpg?retry=2']);
      expect(result.current.imageError).toBe(true);
      expect(onError).toHaveBeenCalledTimes(1);
    });

    it('does not retry when retryOnError is false', () => {
      const { result } = renderHook(() => useProgressiveImageLoader({ src: '/a.jpg', retryOnError: false }));

      failLatest();
      act(() => { vi.advanceTimersByTime(10_000); });

      expect(imageInstances).toHaveLength(1);
      expect(result.current.imageError).toBe(true);
    });

    it('a retry that succeeds loads the original src', () => {
      const onLoad = vi.fn();
      const { result } = renderHook(() => useProgressiveImageLoader({ src: '/a.jpg', onLoad }));

      failLatest();
      act(() => { vi.advanceTimersByTime(1000); });
      act(() => { imageInstances[1]?.onload?.(); });

      expect(result.current.imageLoaded).toBe(true);
      expect(result.current.imageSrc).toBe('/a.jpg');
      expect(onLoad).toHaveBeenCalledTimes(1);
    });

    it('clears the backoff timer on unmount', () => {
      const { unmount } = renderHook(() => useProgressiveImageLoader({ src: '/a.jpg' }));
      failLatest();

      unmount();
      act(() => { vi.advanceTimersByTime(10_000); });

      expect(imageInstances).toHaveLength(1);
    });

    it('a new src starts a fresh sequence and cancels the old timer', () => {
      const { rerender } = renderHook(({ src }) => useProgressiveImageLoader({ src }), {
        initialProps: { src: '/a.jpg' },
      });
      failLatest();

      rerender({ src: '/b.jpg' });
      act(() => { vi.advanceTimersByTime(1000); });

      expect(imageSources).toEqual(['/a.jpg', '/b.jpg']);   // the old retry never fires
    });

    it('does not restart the load when the caller passes new inline callbacks', () => {
      const { rerender } = renderHook(
        ({ n }) => useProgressiveImageLoader({ src: '/a.jpg', onLoad: () => void n, onError: () => void n }),
        { initialProps: { n: 1 } }
      );

      rerender({ n: 2 });
      rerender({ n: 3 });

      expect(imageInstances).toHaveLength(1);
    });
  });
});

