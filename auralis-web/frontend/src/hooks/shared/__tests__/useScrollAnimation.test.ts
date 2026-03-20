/**
 * useScrollAnimation Hook Tests
 *
 * Tests for intersection observer-based scroll animations.
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useScrollAnimation, useStaggerAnimation, useAdvancedScrollAnimation } from '../useScrollAnimation';

// Track IntersectionObserver instances created during tests
let observerInstances: MockIntersectionObserver[] = [];

class MockIntersectionObserver {
  callback: IntersectionObserverCallback;
  options: IntersectionObserverInit | undefined;
  observed: Element[] = [];

  constructor(callback: IntersectionObserverCallback, options?: IntersectionObserverInit) {
    this.callback = callback;
    this.options = options;
    observerInstances.push(this);
  }

  observe(target: Element) {
    this.observed.push(target);
  }

  unobserve(target: Element) {
    this.observed = this.observed.filter((el) => el !== target);
  }

  disconnect() {
    this.observed = [];
  }

  /** Simulate an element entering or leaving the viewport. */
  trigger(entries: Partial<IntersectionObserverEntry>[]) {
    this.callback(
      entries.map((e) => ({
        isIntersecting: false,
        intersectionRatio: 0,
        boundingClientRect: {} as DOMRectReadOnly,
        intersectionRect: {} as DOMRectReadOnly,
        rootBounds: null,
        target: document.createElement('div'),
        time: Date.now(),
        ...e,
      })) as IntersectionObserverEntry[],
      this as unknown as IntersectionObserver
    );
  }
}

beforeEach(() => {
  observerInstances = [];
  vi.stubGlobal('IntersectionObserver', MockIntersectionObserver);
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('useScrollAnimation', () => {
  it('returns a ref', () => {
    const { result } = renderHook(() => useScrollAnimation());
    expect(result.current).toBeDefined();
    expect(result.current).toHaveProperty('current');
  });

  it('creates an IntersectionObserver with default options', () => {
    renderHook(() => useScrollAnimation());

    expect(observerInstances.length).toBeGreaterThanOrEqual(1);
    const obs = observerInstances[observerInstances.length - 1];
    expect(obs.options?.threshold).toBe(0.1);
    expect(obs.options?.rootMargin).toBe('0px');
  });

  it('uses custom threshold and rootMargin', () => {
    renderHook(() =>
      useScrollAnimation({ threshold: 0.5, rootMargin: '10px' })
    );

    const obs = observerInstances[observerInstances.length - 1];
    expect(obs.options?.threshold).toBe(0.5);
    expect(obs.options?.rootMargin).toBe('10px');
  });

  it('adds animation class when element intersects', () => {
    const { result } = renderHook(() => useScrollAnimation());

    // Simulate a mounted element
    const el = document.createElement('div');
    (result.current as React.MutableRefObject<HTMLDivElement | null>).current = el;

    // Re-render to pick up ref
    renderHook(() => useScrollAnimation());
    const obs = observerInstances[observerInstances.length - 1];

    obs.trigger([{ isIntersecting: true, target: el }]);

    expect(el.classList.contains('animate-fade-in')).toBe(true);
  });

  it('uses a custom animation class', () => {
    const el = document.createElement('div');

    const { result } = renderHook(() =>
      useScrollAnimation({ animationClass: 'custom-anim' })
    );

    (result.current as React.MutableRefObject<HTMLDivElement | null>).current = el;
    renderHook(() => useScrollAnimation({ animationClass: 'custom-anim' }));
    const obs = observerInstances[observerInstances.length - 1];

    obs.trigger([{ isIntersecting: true, target: el }]);

    expect(el.classList.contains('custom-anim')).toBe(true);
  });

  it('unobserves after first trigger when once=true (default)', () => {
    const el = document.createElement('div');

    renderHook(() => useScrollAnimation());
    const obs = observerInstances[observerInstances.length - 1];
    obs.observed.push(el);

    obs.trigger([{ isIntersecting: true, target: el }]);

    // The observer's unobserve was called, removing from observed
    expect(obs.observed).not.toContain(el);
  });

  it('removes class when out of view if once=false', () => {
    const el = document.createElement('div');

    renderHook(() => useScrollAnimation({ once: false }));
    const obs = observerInstances[observerInstances.length - 1];

    // Enter
    obs.trigger([{ isIntersecting: true, target: el }]);
    expect(el.classList.contains('animate-fade-in')).toBe(true);

    // Leave
    obs.trigger([{ isIntersecting: false, target: el }]);
    expect(el.classList.contains('animate-fade-in')).toBe(false);
  });

  it('disconnects on unmount', () => {
    const { unmount } = renderHook(() => useScrollAnimation());
    const obs = observerInstances[observerInstances.length - 1];

    const disconnectSpy = vi.spyOn(obs, 'disconnect');
    unmount();
    expect(disconnectSpy).toHaveBeenCalled();
  });
});

describe('useStaggerAnimation', () => {
  it('returns refs and setRef', () => {
    const { result } = renderHook(() => useStaggerAnimation());

    expect(result.current.refs).toBeDefined();
    expect(typeof result.current.setRef).toBe('function');
  });

  it('setRef stores elements at correct indices', () => {
    const { result } = renderHook(() => useStaggerAnimation({ delay: 50 }));

    const el0 = document.createElement('div');
    const el1 = document.createElement('div');
    result.current.setRef(el0, 0);
    result.current.setRef(el1, 1);

    expect(result.current.refs.current[0]).toBe(el0);
    expect(result.current.refs.current[1]).toBe(el1);
  });
});

describe('useAdvancedScrollAnimation', () => {
  it('maps animation type to correct class', () => {
    const el = document.createElement('div');

    renderHook(() => useAdvancedScrollAnimation({ animation: 'scale-in' }));
    const obs = observerInstances[observerInstances.length - 1];

    obs.trigger([{ isIntersecting: true, target: el }]);

    expect(el.classList.contains('animate-scale-in')).toBe(true);
  });

  it('defaults to fade-in-up animation', () => {
    const el = document.createElement('div');

    renderHook(() => useAdvancedScrollAnimation());
    const obs = observerInstances[observerInstances.length - 1];

    obs.trigger([{ isIntersecting: true, target: el }]);

    expect(el.classList.contains('animate-fade-in-up')).toBe(true);
  });
});
