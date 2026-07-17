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

// Mutable player state so individual tests can toggle playback (#4481: the
// decay branch only runs when isPlaying flips false). Hoisted so the mock
// factory — which vitest hoists above imports — can close over it.
// NOTE: the shape must match the real selectors — selectEnhancedStreamingState
// reads state.player.streaming.enhanced.state. The prior inline mock provided
// `streaming: { state: null }` (no `enhanced`), which made EVERY test in this
// file throw at render — a pre-existing breakage fixed here alongside #4481.
const { mockPlayerState } = vi.hoisted(() => ({
  mockPlayerState: {
    isPlaying: true,
    streaming: { enhanced: { state: null as string | null } },
  },
}));

// Mock redux so the hook doesn't need a real store
vi.mock('react-redux', () => ({
  useSelector: vi.fn((selector: (s: any) => any) =>
    selector({ player: mockPlayerState })
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

    // Reset playback to the default (playing) state for every test.
    mockPlayerState.isPlaying = true;
    mockPlayerState.streaming.enhanced.state = null;

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
    window.__auralisAudioContext = makeFakeAudioContext();
    window.__auralisAnalyser = makeFakeAnalyser(128);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    delete window.__auralisAudioContext;
    delete window.__auralisAnalyser;
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
    window.__auralisAnalyser = makeFakeAnalyser(0);

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
    window.__auralisAnalyser = makeFakeAnalyser(200);

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
    window.__auralisAnalyser = makeFakeAnalyser(200);

    const { result } = renderHook(() => useAudioVisualization(true));

    act(() => {
      runFrames(rafCallbacks, 4, 0, 12, performanceNowRef);
    });

    expect(result.current.isActive).toBe(true);
  });

  // ============================================================================
  // 5. No-AudioContext polling branch (#4481)
  // ============================================================================

  it('polls for an AudioContext when none exists yet, then stops once found (#4481)', () => {
    // Enter the init effect with NO global context so the polling branch runs
    // (useAudioVisualization.ts:158-171). beforeEach installed one — remove it.
    delete window.__auralisAudioContext;
    delete window.__auralisAnalyser;

    const intervals = new Map<number, () => void>();
    let intervalId = 1;
    const setIntervalSpy = vi
      .spyOn(window, 'setInterval')
      .mockImplementation(((cb: () => void) => {
        const id = intervalId++;
        intervals.set(id, cb);
        return id;
      }) as unknown as typeof window.setInterval);
    const clearIntervalSpy = vi
      .spyOn(window, 'clearInterval')
      .mockImplementation(((id: number) => {
        intervals.delete(id);
      }) as unknown as typeof window.clearInterval);

    const { unmount } = renderHook(() => useAudioVisualization(true));

    // No context at mount → a 500ms poll was scheduled.
    expect(setIntervalSpy).toHaveBeenCalledWith(expect.any(Function), 500);
    expect(intervals.size).toBe(1);

    // First poll: still no context → nothing created, interval keeps running.
    act(() => {
      for (const cb of [...intervals.values()]) cb();
    });
    expect(window.__auralisAnalyser).toBeUndefined();
    expect(clearIntervalSpy).not.toHaveBeenCalled();

    // Context appears → next poll wires up the analyser and clears the interval.
    window.__auralisAudioContext = {
      sampleRate: 44100,
      createAnalyser: () => makeFakeAnalyser(128),
    } as unknown as AudioContext;
    act(() => {
      for (const cb of [...intervals.values()]) cb();
    });
    expect(window.__auralisAnalyser).toBeDefined();
    expect(clearIntervalSpy).toHaveBeenCalled();

    // Unmount runs the effect cleanup path without throwing.
    unmount();
  });

  // ============================================================================
  // 6. Decay-to-DEFAULT_DATA branch when playback stops (#4481)
  // ============================================================================

  it('decays smoothed values to default after playback stops (#4481)', () => {
    // Build up non-trivial smoothed values while "playing" loud audio.
    window.__auralisAnalyser = makeFakeAnalyser(200);

    const { result, rerender } = renderHook(() => useAudioVisualization(true));

    act(() => {
      runFrames(rafCallbacks, 12, 0, 40, performanceNowRef);
    });

    expect(result.current.isActive).toBe(true);
    const builtUpLoudness = result.current.loudness;
    expect(builtUpLoudness).toBeGreaterThan(0);

    // Stop playback → the start/stop effect enters the decay branch
    // (useAudioVisualization.ts:276-300).
    act(() => {
      mockPlayerState.isPlaying = false;
      rerender();
    });

    // A few decay frames: values fade but are still non-zero and marked inactive.
    act(() => {
      runFrames(rafCallbacks, 3, 0, 16, performanceNowRef);
    });
    expect(result.current.isActive).toBe(false);
    expect(result.current.loudness).toBeGreaterThan(0);
    expect(result.current.loudness).toBeLessThan(builtUpLoudness);

    // Many more frames: fully decays to DEFAULT_DATA.
    act(() => {
      runFrames(rafCallbacks, 300, 0, 16, performanceNowRef);
    });
    expect(result.current.loudness).toBe(0);
    expect(result.current.isActive).toBe(false);
  });
});
