/**
 * StarfieldBackground render-loop gating (#5661)
 *
 * One rAF loop drives the analyser sampling and the draw, capped to ~30fps
 * while animating, and is cancelled — not left spinning on early returns —
 * when nothing moves: audio settled, prefers-reduced-motion, a hidden tab,
 * or the light theme. These tests pin the scheduling behaviour with a fake
 * WebGL context and a manual rAF clock.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { act } from '@testing-library/react';
import { render, cleanup } from '@/test/test-utils';
import { StarfieldBackground } from '../StarfieldBackground';
import {
  setAudioVisualizationActive,
  resetAudioVisualizationModuleForTests,
} from '@/hooks/audio/audioVisualization';

const { themeState } = vi.hoisted(() => ({
  themeState: { mode: 'dark' as string },
}));

vi.mock('@/contexts/ThemeContext', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/contexts/ThemeContext')>()),
  useTheme: () => ({
    mode: themeState.mode,
    toggleTheme: vi.fn(),
    setTheme: vi.fn(),
  }),
}));

function makeFakeGL(): WebGLRenderingContext {
  return {
    createShader: vi.fn(() => ({})),
    shaderSource: vi.fn(),
    compileShader: vi.fn(),
    getShaderParameter: vi.fn(() => true),
    deleteShader: vi.fn(),
    createProgram: vi.fn(() => ({})),
    attachShader: vi.fn(),
    linkProgram: vi.fn(),
    getProgramParameter: vi.fn(() => true),
    getUniformLocation: vi.fn(() => ({})),
    createBuffer: vi.fn(() => ({})),
    bindBuffer: vi.fn(),
    bufferData: vi.fn(),
    getAttribLocation: vi.fn(() => 0),
    enableVertexAttribArray: vi.fn(),
    vertexAttribPointer: vi.fn(),
    deleteProgram: vi.fn(),
    useProgram: vi.fn(),
    uniform1f: vi.fn(),
    uniform2f: vi.fn(),
    viewport: vi.fn(),
    drawArrays: vi.fn(),
  } as unknown as WebGLRenderingContext;
}

function makeLoudAnalyser(): AnalyserNode {
  return {
    fftSize: 2048,
    frequencyBinCount: 1024,
    smoothingTimeConstant: 0.8,
    getByteFrequencyData: vi.fn((buf: Uint8Array) => buf.fill(200)),
  } as unknown as AnalyserNode;
}

describe('StarfieldBackground render loop (#5661)', () => {
  let rafCallbacks: Map<number, FrameRequestCallback>;
  let rafIdCounter: number;
  let fakeGL: WebGLRenderingContext;
  let clock: { now: number };
  let realGetContext: PropertyDescriptor | undefined;
  let realMatchMedia: typeof window.matchMedia;

  beforeEach(() => {
    themeState.mode = 'dark';
    resetAudioVisualizationModuleForTests();
    delete (window as any).__auralisAnalyser;
    delete (window as any).__auralisAudioContext;

    rafCallbacks = new Map();
    rafIdCounter = 1;
    clock = { now: 0 };
    realMatchMedia = window.matchMedia;

    vi.spyOn(window, 'requestAnimationFrame').mockImplementation((cb) => {
      const id = rafIdCounter++;
      rafCallbacks.set(id, cb);
      return id;
    });
    vi.spyOn(window, 'cancelAnimationFrame').mockImplementation((id) => {
      rafCallbacks.delete(id);
    });
    vi.spyOn(performance, 'now').mockImplementation(() => clock.now);

    fakeGL = makeFakeGL();
    realGetContext = Object.getOwnPropertyDescriptor(
      HTMLCanvasElement.prototype,
      'getContext'
    );
    Object.defineProperty(HTMLCanvasElement.prototype, 'getContext', {
      value: vi.fn(() => fakeGL),
      configurable: true,
    });
  });

  afterEach(() => {
    if (realGetContext) {
      Object.defineProperty(HTMLCanvasElement.prototype, 'getContext', realGetContext);
    }
    // The reduced-motion test swaps window.matchMedia by assignment, which
    // vi.restoreAllMocks does not undo.
    window.matchMedia = realMatchMedia;
    vi.restoreAllMocks();
    cleanup();
  });

  /** Drive every scheduled frame, advancing the clock by `stepMs`. */
  function tick(stepMs: number): void {
    clock.now += stepMs;
    for (const id of [...rafCallbacks.keys()]) {
      const cb = rafCallbacks.get(id)!;
      rafCallbacks.delete(id);
      cb(clock.now);
    }
  }

  it('mounts nothing in the light theme', () => {
    themeState.mode = 'light';

    const { container } = render(<StarfieldBackground />);

    expect(container.querySelector('canvas')).toBeNull();
    expect(fakeGL.drawArrays).not.toHaveBeenCalled();
    expect(rafCallbacks.size).toBe(0);
  });

  it('schedules no loop under prefers-reduced-motion and draws one static frame', () => {
    window.matchMedia = vi.fn((query: string) => ({
      matches: query.includes('prefers-reduced-motion: reduce'),
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })) as unknown as typeof window.matchMedia;

    render(<StarfieldBackground />);

    expect(rafCallbacks.size).toBe(0);
    expect(fakeGL.drawArrays).toHaveBeenCalledTimes(1);

    // Time passes; the frozen frame is not redrawn
    clock.now += 5000;
    expect(fakeGL.drawArrays).toHaveBeenCalledTimes(1);
  });

  it('stops the loop after one static frame when audio is settled-idle', () => {
    render(<StarfieldBackground />);

    // First frame samples (idle → settled immediately) and draws once.
    tick(16);
    expect(fakeGL.drawArrays).toHaveBeenCalledTimes(1);
    expect(rafCallbacks.size).toBe(0);

    // Time passes; nothing reschedules.
    clock.now += 5000;
    tick(16);
    expect(fakeGL.drawArrays).toHaveBeenCalledTimes(1);
    expect(rafCallbacks.size).toBe(0);
  });

  it('restarts when playback becomes active, then caps draws to ~30fps', () => {
    render(<StarfieldBackground />);
    tick(16); // settle to idle
    const scheduledThroughIdle = rafIdCounter;

    // Playback starts: the wake-up must reschedule, not stay dead.
    (window as any).__auralisAnalyser = makeLoudAnalyser();
    (window as any).__auralisAudioContext = { sampleRate: 44100 };
    act(() => {
      setAudioVisualizationActive(true);
    });

    // The isActive flip re-rendered and restarted the loop.
    tick(16);
    expect(rafIdCounter).toBeGreaterThan(scheduledThroughIdle);
    expect(rafCallbacks.size).toBe(1); // animating again

    // 60 ticks at 60fps → at most ~31 draws (30fps cap).
    const drawCalls = fakeGL.drawArrays as unknown as ReturnType<typeof vi.fn>;
    const drawsAtStart = drawCalls.mock.calls.length;
    for (let i = 0; i < 60; i++) tick(1000 / 60);
    const drawsDuring = drawCalls.mock.calls.length - drawsAtStart;
    expect(drawsDuring).toBeLessThanOrEqual(32);
    expect(drawsDuring).toBeGreaterThan(10);
  });

  it('cancels the loop while the tab is hidden and resumes on return', () => {
    render(<StarfieldBackground />);

    (window as any).__auralisAnalyser = makeLoudAnalyser();
    (window as any).__auralisAudioContext = { sampleRate: 44100 };
    act(() => {
      setAudioVisualizationActive(true);
    });
    tick(16);
    expect(rafCallbacks.size).toBe(1);

    // Hide: the current tick cancels itself without rescheduling.
    vi.spyOn(document, 'hidden', 'get').mockReturnValue(true);
    tick(16);
    expect(rafCallbacks.size).toBe(0);

    // Time passes hidden: no draws, no scheduling.
    clock.now += 5000;
    tick(16);
    expect(rafCallbacks.size).toBe(0);

    // Return: the visibilitychange restart brings the loop back.
    vi.spyOn(document, 'hidden', 'get').mockReturnValue(false);
    document.dispatchEvent(new Event('visibilitychange'));
    expect(rafCallbacks.size).toBe(1);
  });
});
