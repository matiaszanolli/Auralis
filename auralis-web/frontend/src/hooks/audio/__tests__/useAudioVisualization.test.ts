/**
 * useAudioVisualization hook tests
 *
 * After #5664 the hook only wires playback state to the visualization
 * store's active flag and ensures the analyser exists — it runs no loop and
 * returns the stable store object, so it never re-renders its host.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { renderHook } from '@testing-library/react';

const { mockPlayerState } = vi.hoisted(() => ({
  mockPlayerState: {
    isPlaying: true,
    streaming: { enhanced: { state: null as string | null } },
  },
}));

vi.mock('react-redux', () => ({
  useSelector: vi.fn((selector: (s: any) => any) =>
    selector({ player: mockPlayerState })
  ),
}));

import { useAudioVisualization } from '../useAudioVisualization';
import {
  getAudioVisualization,
  resetAudioVisualizationModuleForTests,
} from '../audioVisualization';
import * as audioVisualization from '../audioVisualization';

describe('useAudioVisualization (#5664 store model)', () => {
  beforeEach(() => {
    resetAudioVisualizationModuleForTests();
    delete (window as any).__auralisAnalyser;
    delete (window as any).__auralisAudioContext;
    mockPlayerState.isPlaying = true;
    mockPlayerState.streaming.enhanced.state = null;
  });

  it('returns the stable store object and never re-renders while audio plays', () => {
    let renderCount = 0;
    const { result } = renderHook(() => {
      renderCount++;
      return useAudioVisualization(true);
    });

    expect(result.current).toBe(getAudioVisualization());
    expect(renderCount).toBe(1);
  });

  it('flags the sampler active while playing and inactive when paused', () => {
    const setActiveSpy = vi.spyOn(audioVisualization, 'setAudioVisualizationActive');

    const { rerender } = renderHook(() => useAudioVisualization(true));
    expect(setActiveSpy).toHaveBeenLastCalledWith(true);

    mockPlayerState.isPlaying = false;
    rerender();
    expect(setActiveSpy).toHaveBeenLastCalledWith(false);
  });

  it('never flags active when enabled=false', () => {
    const setActiveSpy = vi.spyOn(audioVisualization, 'setAudioVisualizationActive');

    renderHook(() => useAudioVisualization(false));
    expect(setActiveSpy).toHaveBeenLastCalledWith(false);
  });

  it('polls for an AudioContext when none exists yet, then stops once found (#4481)', () => {
    const intervals = new Map<number, () => void>();
    let intervalId = 1;
    vi.spyOn(window, 'setInterval').mockImplementation(((cb: () => void) => {
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

    expect(intervals.size).toBe(1);

    // Context appears → next poll wires up the analyser and clears the interval.
    (window as any).__auralisAudioContext = {
      sampleRate: 44100,
      createAnalyser: () =>
        ({
          fftSize: 2048,
          frequencyBinCount: 1024,
          smoothingTimeConstant: 0.8,
        }) as unknown as AnalyserNode,
    } as unknown as AudioContext;
    for (const cb of [...intervals.values()]) cb();

    expect((window as any).__auralisAnalyser).toBeDefined();
    expect(clearIntervalSpy).toHaveBeenCalled();

    unmount();
  });
});
