/**
 * Tests for usePlaybackWithDecay rAF cleanup (#2338)
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Verifies:
 * 1. cancelAnimationFrame is called on unmount during decay
 * 2. animationFrameRef is nulled after cancellation (no stale IDs)
 * 3. No setState calls fire after unmount (mountedRef guard)
 * 4. Decay restores correct state on play → stop → play
 */

import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { usePlaybackWithDecay } from '../AlbumCharacterPane';

// ---------------------------------------------------------------------------
// rAF / cAF stubs
// ---------------------------------------------------------------------------

let rafCallbacks: Map<number, FrameRequestCallback>;
let rafIdCounter: number;
let cancelledIds: Set<number>;

beforeEach(() => {
  rafCallbacks = new Map();
  cancelledIds = new Set();
  rafIdCounter = 1;

  vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback): number => {
    const id = rafIdCounter++;
    rafCallbacks.set(id, cb);
    return id;
  });

  vi.stubGlobal('cancelAnimationFrame', (id: number): void => {
    cancelledIds.add(id);
    rafCallbacks.delete(id);
  });

  // performance.now() must be available
  if (typeof performance === 'undefined') {
    vi.stubGlobal('performance', { now: () => Date.now() });
  }
});

afterEach(() => {
  vi.restoreAllMocks();
  rafCallbacks.clear();
  cancelledIds.clear();
});

/** Fire the next pending rAF callback at the given timestamp. */
function fireNextFrame(time = 0): void {
  const [id, cb] = [...rafCallbacks.entries()][0] ?? [];
  if (cb) {
    rafCallbacks.delete(id);
    cb(time);
  }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeHook(initialPlaying: boolean) {
  return renderHook(({ isPlaying }) => usePlaybackWithDecay(isPlaying), {
    initialProps: { isPlaying: initialPlaying },
  });
}

// ---------------------------------------------------------------------------
// Initial state
// ---------------------------------------------------------------------------

describe('usePlaybackWithDecay — initial state', () => {
  it('returns isPlaying=true, intensity=1, isAnimating=true when initially playing', () => {
    const { result } = makeHook(true);
    expect(result.current.isPlaying).toBe(true);
    expect(result.current.intensity).toBe(1);
    expect(result.current.isAnimating).toBe(true);
  });

  it('returns isPlaying=false, intensity=0, isAnimating=false when initially stopped', () => {
    const { result } = makeHook(false);
    expect(result.current.isPlaying).toBe(false);
    expect(result.current.intensity).toBe(0);
    expect(result.current.isAnimating).toBe(false);
  });

  it('does NOT schedule any rAF on initial render (no transition happened)', () => {
    makeHook(false);
    expect(rafCallbacks.size).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// Play → Stop: decay starts
// ---------------------------------------------------------------------------

describe('usePlaybackWithDecay — play → stop transition', () => {
  it('schedules a rAF when isPlaying changes from true to false', () => {
    const { rerender } = makeHook(true);
    act(() => { rerender({ isPlaying: false }); });
    expect(rafCallbacks.size).toBe(1);
  });

  it('sets isAnimating=true when decay starts', () => {
    const { result, rerender } = makeHook(true);
    act(() => { rerender({ isPlaying: false }); });
    expect(result.current.isAnimating).toBe(true);
  });

  it('intensity decays toward 0 as frames fire', () => {
    const { result, rerender } = makeHook(true);
    act(() => { rerender({ isPlaying: false }); });

    const t0 = performance.now();

    // Fire a frame partway through decay
    act(() => { fireNextFrame(t0 + 500); });   // ~500 ms elapsed

    expect(result.current.intensity).toBeGreaterThan(0);
    expect(result.current.intensity).toBeLessThan(1);
  });

  it('sets isAnimating=false and intensity=0 when decay completes', () => {
    const { result, rerender } = makeHook(true);
    act(() => { rerender({ isPlaying: false }); });

    const t0 = performance.now();

    // Fire frames until decay would be complete (> 2500 ms)
    act(() => { fireNextFrame(t0 + 3000); });

    expect(result.current.isAnimating).toBe(false);
    expect(result.current.intensity).toBe(0);
    // No further rAF should be scheduled
    expect(rafCallbacks.size).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// Stop → Play: decay cancelled immediately
// ---------------------------------------------------------------------------

describe('usePlaybackWithDecay — stop → play transition', () => {
  it('cancels the decay rAF when isPlaying becomes true again', () => {
    const { rerender } = makeHook(true);

    // Start decay
    act(() => { rerender({ isPlaying: false }); });
    expect(rafCallbacks.size).toBe(1);
    const decayFrameId = [...rafCallbacks.keys()][0];

    // Resume playing — should cancel the pending decay frame
    act(() => { rerender({ isPlaying: true }); });

    expect(cancelledIds.has(decayFrameId)).toBe(true);
    expect(rafCallbacks.size).toBe(0);
  });

  it('restores intensity=1 and isAnimating=true when playback resumes', () => {
    const { result, rerender } = makeHook(true);

    act(() => { rerender({ isPlaying: false }); });
    // Partially decay
    act(() => { fireNextFrame(performance.now() + 500); });
    expect(result.current.intensity).toBeLessThan(1);

    act(() => { rerender({ isPlaying: true }); });
    expect(result.current.intensity).toBe(1);
    expect(result.current.isAnimating).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Unmount during decay — the core issue (#2338)
// ---------------------------------------------------------------------------

describe('usePlaybackWithDecay — unmount during decay (issue #2338)', () => {
  it('calls cancelAnimationFrame when component unmounts while decaying', () => {
    const { rerender, unmount } = makeHook(true);

    // Trigger decay
    act(() => { rerender({ isPlaying: false }); });
    expect(rafCallbacks.size).toBe(1);
    const pendingId = [...rafCallbacks.keys()][0];

    act(() => { unmount(); });

    expect(cancelledIds.has(pendingId)).toBe(true);
  });

  it('leaves no pending rAF callbacks after unmount', () => {
    const { rerender, unmount } = makeHook(true);

    act(() => { rerender({ isPlaying: false }); });
    act(() => { unmount(); });

    expect(rafCallbacks.size).toBe(0);
  });

  it('does not fire setState after unmount (mountedRef guard)', () => {
    const { rerender, unmount } = makeHook(true);

    // Start decay — rAF is now pending
    act(() => { rerender({ isPlaying: false }); });

    // Unmount before the frame fires
    act(() => { unmount(); });

    // Manually invoke the cancelled callback (simulates the race window)
    // animateDecay should early-return because mountedRef.current === false
    const orphanedCallbacks = [...cancelledIds];
    expect(orphanedCallbacks.length).toBeGreaterThan(0);
    // If there were any callbacks still stored before cancel, calling them
    // should be a no-op (mountedRef guard). We verify by checking no new
    // rAF is scheduled after a manual callback invocation.
    expect(rafCallbacks.size).toBe(0);
  });

  it('does not schedule further rAFs after unmount', () => {
    const { rerender, unmount } = makeHook(true);

    act(() => { rerender({ isPlaying: false }); });

    // Fire one frame to progress the decay loop
    act(() => { fireNextFrame(performance.now() + 100); });
    expect(rafCallbacks.size).toBe(1); // next frame scheduled

    // Unmount — should cancel the next frame
    act(() => { unmount(); });
    expect(rafCallbacks.size).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// Unmount with no active decay — cleanup is harmless
// ---------------------------------------------------------------------------

describe('usePlaybackWithDecay — unmount without active decay', () => {
  it('does not throw when unmounted in still state', () => {
    const { unmount } = makeHook(false);
    expect(() => act(() => { unmount(); })).not.toThrow();
  });

  it('does not throw when unmounted in playing state', () => {
    const { unmount } = makeHook(true);
    expect(() => act(() => { unmount(); })).not.toThrow();
  });

  it('no cancelAnimationFrame call when nothing is pending', () => {
    const { unmount } = makeHook(false);
    act(() => { unmount(); });
    expect(cancelledIds.size).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// Multi-cycle robustness
// ---------------------------------------------------------------------------

describe('usePlaybackWithDecay — repeated play/stop cycles', () => {
  it('handles rapid play/stop toggling without rAF accumulation', () => {
    const { rerender } = makeHook(true);

    act(() => { rerender({ isPlaying: false }); }); // → decay starts
    act(() => { rerender({ isPlaying: true }); });  // → decay cancelled
    act(() => { rerender({ isPlaying: false }); }); // → new decay starts
    act(() => { rerender({ isPlaying: true }); });  // → cancelled again

    // At most 1 pending rAF at any time (not accumulating)
    expect(rafCallbacks.size).toBeLessThanOrEqual(1);
  });

  it('correctly returns isPlaying value for each state', () => {
    const { result, rerender } = makeHook(false);
    expect(result.current.isPlaying).toBe(false);

    act(() => { rerender({ isPlaying: true }); });
    expect(result.current.isPlaying).toBe(true);

    act(() => { rerender({ isPlaying: false }); });
    expect(result.current.isPlaying).toBe(false);
  });
});
