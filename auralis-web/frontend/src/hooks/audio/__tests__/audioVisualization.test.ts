/**
 * Audio visualization store + sampler tests
 *
 * Since #5664 the analyser data travels through the mutable store in
 * audioVisualization.ts instead of React state — the starfield reads it in
 * its own rAF loop, so no component re-renders while music plays. The
 * sampler is driven by that loop (one call per frame), throttled to ~30Hz.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  getAudioVisualization,
  sampleAudioVisualization,
  setAudioVisualizationActive,
  subscribeToIsActive,
  resetAudioVisualizationModuleForTests,
} from '../audioVisualization';

function makeFakeAnalyser(value = 128): AnalyserNode {
  return {
    fftSize: 2048,
    frequencyBinCount: 1024,
    smoothingTimeConstant: 0.8,
    getByteFrequencyData: vi.fn((buf: Uint8Array) => buf.fill(value)),
  } as unknown as AnalyserNode;
}

/** Install a loud fake analyser and mark audio active. */
function primeLoudAudio(value = 200): AnalyserNode {
  const analyser = makeFakeAnalyser(value);
  (window as any).__auralisAnalyser = analyser;
  (window as any).__auralisAudioContext = { sampleRate: 44100 };
  setAudioVisualizationActive(true);
  return analyser;
}

describe('audioVisualization sampler/store (#5664)', () => {
  beforeEach(() => {
    resetAudioVisualizationModuleForTests();
    delete (window as any).__auralisAnalyser;
    delete (window as any).__auralisAudioContext;
  });

  it('starts at the default data shape', () => {
    expect(getAudioVisualization()).toEqual({
      bass: 0,
      mid: 0,
      treble: 0,
      loudness: 0,
      peak: 0,
      isActive: false,
    });
  });

  it('throttles analyser reads to ~30Hz regardless of loop rate', () => {
    const analyser = primeLoudAudio();

    sampleAudioVisualization(0);
    sampleAudioVisualization(10); // inside the 33ms gate — skipped
    sampleAudioVisualization(20); // skipped
    expect(vi.mocked(analyser.getByteFrequencyData)).toHaveBeenCalledTimes(1);

    sampleAudioVisualization(40); // past the gate — sampled
    expect(vi.mocked(analyser.getByteFrequencyData)).toHaveBeenCalledTimes(2);
    expect(getAudioVisualization().isActive).toBe(true);
  });

  it('returns a stable store reference while values mutate in place', () => {
    primeLoudAudio();
    const before = getAudioVisualization();

    sampleAudioVisualization(0);
    sampleAudioVisualization(100);

    expect(getAudioVisualization()).toBe(before);
    expect(before.isActive).toBe(true);
    expect(before.loudness).toBeGreaterThan(0);
  });

  it('decays toward the defaults after audio goes inactive, then reports settled', () => {
    primeLoudAudio();

    // Build up non-trivial values while active
    for (let i = 0; i < 12; i++) {
      sampleAudioVisualization(i * 40);
    }
    const builtUp = getAudioVisualization().loudness;
    expect(builtUp).toBeGreaterThan(0);

    setAudioVisualizationActive(false);

    // A few decay frames: still fading
    let settled = false;
    for (let i = 0; i < 3; i++) {
      settled = sampleAudioVisualization(1000 + i * 40);
    }
    expect(getAudioVisualization().isActive).toBe(false);
    expect(getAudioVisualization().loudness).toBeGreaterThan(0);
    expect(getAudioVisualization().loudness).toBeLessThan(builtUp);
    expect(settled).toBe(false);

    // Many more frames: fully settled → the render loop may stop (#5661)
    settled = true;
    for (let i = 0; i < 400; i++) {
      settled = sampleAudioVisualization(2000 + i * 40);
    }
    expect(settled).toBe(true);
    expect(getAudioVisualization().loudness).toBe(0);
    expect(getAudioVisualization().isActive).toBe(false);
  });

  it('notifies isActive subscribers only on transitions', () => {
    const listener = vi.fn();
    const unsubscribe = subscribeToIsActive(listener);

    primeLoudAudio();
    sampleAudioVisualization(0);
    sampleAudioVisualization(100);

    // One flip false→true; repeated active samples do not re-notify
    expect(listener).toHaveBeenCalledTimes(1);

    setAudioVisualizationActive(false);
    sampleAudioVisualization(200);
    expect(listener).toHaveBeenCalledTimes(2);

    unsubscribe();
    setAudioVisualizationActive(true);
    sampleAudioVisualization(300);
    expect(listener).toHaveBeenCalledTimes(2);
  });
});
