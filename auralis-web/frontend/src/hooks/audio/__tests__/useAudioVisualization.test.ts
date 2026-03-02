/**
 * Tests for useAudioVisualization hook
 *
 * Verifies that state updates are throttled to ~30fps and that
 * insignificant value changes do not trigger re-renders.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';

// ============================================================================
// Module mocking — must come before imports of the module under test
// ============================================================================

// Mock redux so the hook doesn't need a real store
vi.mock('react-redux', () => ({
  useSelector: vi.fn((selector: (s: any) => any) =>
    selector({ player: { isPlaying: true, streaming: { state: null } } })
  ),
}));

import { useAudioVisualization } from '../useAudioVisualization';

// ============================================================================
// Helpers
// ============================================================================

/** Build a fake AnalyserNode whose getByteFrequencyData fills the buffer with `value` */
function makeFakeAnalyser(value = 128): AnalyserNode {
  const bufferLength = 1024;
  const fakeAnalyser = {
    fftSize: 2048,
    frequencyBinCount: bufferLength,
    smoothingTimeConstant: 0.8,
    getByteFrequencyData: vi.fn((buf: Uint8Array) => buf.fill(value)),
  } as unknown as AnalyserNode;
  return fakeAnalyser;
}

/** Fake AudioContext */
function makeFakeAudioContext(sampleRate = 44100): AudioContext {
  return { sampleRate } as unknown as AudioContext;
}

/** Advance fake rAF loop by `frames` ticks, each separated by `msPerFrame` ms */
function runFrames(
  rafCallbacks: Map<number, FrameRequestCallback>,
  frames: number,
  startMs: number,
  msPerFrame: number,
  performanceNowRef: { value: number }
): void {
  for (let i = 0; i < frames; i++) {
    performanceNowRef.value = startMs + i * msPerFrame;
    const ids = [...rafCallbacks.keys()];
    for (const id of ids) {
      const cb = rafCallbacks.get(id)!;
      rafCallbacks.delete(id);
      cb(performanceNowRef.value);
    }
  }
}

// ============================================================================
// Tests
// ============================================================================

describe('useAudioVisualization', () => {
  let rafCallbacks: Map<number, FrameRequestCallback>;
  let rafIdCounter: number;
  let performanceNowRef: { value: number };

  beforeEach(() => {
    rafCallbacks = new Map();
    rafIdCounter = 1;
    performanceNowRef = { value: 0 };

    // Intercept rAF
    vi.spyOn(window, 'requestAnimationFrame').mockImplementation((cb) => {
      const id = rafIdCounter++;
      rafCallbacks.set(id, cb);
      return id;
    });
    vi.spyOn(window, 'cancelAnimationFrame').mockImplementation((id) => {
      rafCallbacks.delete(id);
    });

    // Intercept performance.now()
    vi.spyOn(performance, 'now').mockImplementation(() => performanceNowRef.value);

    // Install fake audio context and analyser on window globals
    (window as any).__auralisAudioContext = makeFakeAudioContext();
    (window as any).__auralisAnalyser = makeFakeAnalyser(128);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    delete (window as any).__auralisAudioContext;
    delete (window as any).__auralisAnalyser;
  });

  // ============================================================================
  // 1. 30fps cap
  // ============================================================================

  it('emits fewer than 200 state updates over 5s at 60fps', () => {
    let renderCount = 0;

    renderHook(() => {
      renderCount++;
      return useAudioVisualization(true);
    });

    // Reset: renderHook itself causes an initial render
    renderCount = 0;

    // Simulate 300 rAF callbacks at 60fps (5 seconds)
    act(() => {
      runFrames(rafCallbacks, 300, 0, 1000 / 60, performanceNowRef);
    });

    // At 60fps for 5s we'd get 300 renders without the fix.
    // With 30fps cap: max ~150 renders.
    expect(renderCount).toBeLessThan(200);
    // Sanity: some updates DID occur (audio is active)
    expect(renderCount).toBeGreaterThan(0);
  });

  it('emits at most ~30 state updates per second', () => {
    let renderCount = 0;

    renderHook(() => {
      renderCount++;
      return useAudioVisualization(true);
    });

    renderCount = 0;

    // Simulate 1 second of 60fps frames (60 callbacks)
    act(() => {
      runFrames(rafCallbacks, 60, 0, 1000 / 60, performanceNowRef);
    });

    // Should emit ≤ 30 renders in 1 second (60fps input, 30fps cap)
    expect(renderCount).toBeLessThanOrEqual(31); // +1 tolerance for boundary
  });

  // ============================================================================
  // 2. Delta threshold — no update for negligible changes
  // ============================================================================

  it('does not update state when audio values are below the delta threshold', () => {
    // Fill analyser with near-silence so smoothed values are tiny
    (window as any).__auralisAnalyser = makeFakeAnalyser(0);

    let renderCount = 0;

    const { result } = renderHook(() => {
      renderCount++;
      return useAudioVisualization(true);
    });

    renderCount = 0;

    act(() => {
      // Run just enough frames to pass the 30fps interval (> 33ms)
      runFrames(rafCallbacks, 5, 0, 10, performanceNowRef); // 5 frames × 10ms = 50ms
    });

    // With all-zero audio the delta is 0 — no updates should fire
    expect(renderCount).toBe(0);
    // Data stays at default
    expect(result.current.isActive).toBe(false);
  });

  it('does update state when audio values exceed the delta threshold', () => {
    // Fill analyser with loud audio (value=200) so smoothed delta is large
    (window as any).__auralisAnalyser = makeFakeAnalyser(200);

    let renderCount = 0;

    renderHook(() => {
      renderCount++;
      return useAudioVisualization(true);
    });

    renderCount = 0;

    act(() => {
      // Run 4 frames spanning > 33ms so 30fps gate fires
      runFrames(rafCallbacks, 4, 0, 12, performanceNowRef); // 4 × 12ms = 48ms
    });

    // Audio is loud → delta exceeds threshold → at least one update
    expect(renderCount).toBeGreaterThan(0);
  });

  // ============================================================================
  // 3. Disabled hook never updates
  // ============================================================================

  it('emits no updates when enabled=false', () => {
    let renderCount = 0;

    renderHook(() => {
      renderCount++;
      return useAudioVisualization(false);
    });

    renderCount = 0;

    act(() => {
      runFrames(rafCallbacks, 60, 0, 1000 / 60, performanceNowRef);
    });

    expect(renderCount).toBe(0);
  });

  // ============================================================================
  // 4. Data shape
  // ============================================================================

  it('returns the default data shape on first render', () => {
    const { result } = renderHook(() => useAudioVisualization(true));

    expect(result.current).toMatchObject({
      bass: 0,
      mid: 0,
      treble: 0,
      loudness: 0,
      peak: 0,
      isActive: false,
    });
  });

  it('sets isActive=true after processing audio', () => {
    (window as any).__auralisAnalyser = makeFakeAnalyser(200);

    const { result } = renderHook(() => useAudioVisualization(true));

    act(() => {
      runFrames(rafCallbacks, 4, 0, 12, performanceNowRef);
    });

    expect(result.current.isActive).toBe(true);
  });
});
