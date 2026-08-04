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
});
