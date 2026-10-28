/**
 * usePrefersReducedMotion and the two things it switches off (#5676)
 *
 * The global prefers-reduced-motion CSS rule only neutralises CSS animation; the WebGL starfield's
 * render loop and the album pane's 10 s text rotation are driven from JavaScript.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { act, renderHook, render, screen } from '@testing-library/react';
import { usePrefersReducedMotion } from '../usePrefersReducedMotion';
import { RotatingDescription } from '@/components/library/AlbumCharacterPane/RotatingDescription';

type Listener = (event: { matches: boolean }) => void;

function stubMatchMedia(initial: boolean) {
  const listeners = new Set<Listener>();
  const media = {
    matches: initial,
    addEventListener: (_type: string, fn: Listener) => listeners.add(fn),
    removeEventListener: (_type: string, fn: Listener) => listeners.delete(fn),
  };
  vi.stubGlobal('matchMedia', vi.fn(() => media));
  window.matchMedia = globalThis.matchMedia;
  return {
    set(matches: boolean) {
      media.matches = matches;
      listeners.forEach((fn) => fn({ matches }));
    },
    listenerCount: () => listeners.size,
  };
}

describe('usePrefersReducedMotion', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('reflects the current preference and follows live changes', () => {
    const media = stubMatchMedia(false);
    const { result } = renderHook(() => usePrefersReducedMotion());
    expect(result.current).toBe(false);

    act(() => media.set(true));

    expect(result.current).toBe(true);
  });

  it('starts true when the system already asks for reduced motion', () => {
    stubMatchMedia(true);

    expect(renderHook(() => usePrefersReducedMotion()).result.current).toBe(true);
  });

  it('stops listening on unmount', () => {
    const media = stubMatchMedia(false);
    const { unmount } = renderHook(() => usePrefersReducedMotion());
    expect(media.listenerCount()).toBe(1);

    unmount();

    expect(media.listenerCount()).toBe(0);
  });
});

describe('RotatingDescription with reduced motion', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  const renderRotating = () =>
    render(<RotatingDescription descriptions={['first', 'second']} staticDescription="static" isPlaying />);

  it('rotates every ten seconds by default', () => {
    stubMatchMedia(false);
    renderRotating();
    expect(screen.getByText('first')).toBeInTheDocument();

    act(() => { vi.advanceTimersByTime(10_500); });

    expect(screen.getByText('second')).toBeInTheDocument();
  });

  it('stays on the first description when reduced motion is requested', () => {
    stubMatchMedia(true);
    renderRotating();

    act(() => { vi.advanceTimersByTime(30_000); });

    expect(screen.getByText('first')).toBeInTheDocument();
    expect(screen.queryByText('second')).toBeNull();
  });
});
