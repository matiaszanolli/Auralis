/**
 * A pause issued while the engine is still starting is not lost (#6424)
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * startPlayback() awaits an AudioContext resume (and the worklet load) before the
 * engine reports 'playing'. A pause clicked inside that window used to be a no-op
 * on the engine (nothing playing yet), so the start completed, audio played and the
 * UI flipped back to playing. The real engine, buffer and core hook are used here;
 * only the Web Audio nodes are mocked.
 */

import { ReactNode } from 'react';
import { describe, it, expect, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import playerReducer from '@/store/slices/playerSlice';
import { useAudioStreamingCore, type StreamingCoreOptions } from '../useAudioStreamingCore';
import { AudioPlaybackEngine } from '@/services/audio/AudioPlaybackEngine';
import { PCMStreamBuffer } from '@/services/audio/PCMStreamBuffer';

const SAMPLE_RATE = 48000;
const CHANNELS = 2;

const OPTIONS: StreamingCoreOptions = {
  streamType: 'enhanced',
  sendType: 'play_enhanced',
  logPrefix: '[test]',
  getStartThreshold: () => 1,
  throttleProgress: true,
  detectOutOfSequence: true,
  closeContextOnCleanup: false,
};

const WS = {
  isConnected: true,
  connectionStatus: 'connected' as const,
  subscribe: vi.fn(() => () => {}),
  subscribeAll: vi.fn(() => () => {}),
  send: vi.fn(),
  connect: vi.fn(),
  disconnect: vi.fn(),
  setResumePositionGetter: vi.fn(),
  reissueActiveStreamAs: vi.fn(() => false),
};

/** An AudioContext whose resume() the test releases, holding startPlayback in its window. */
function suspendedContext() {
  const gain = { gain: { value: 1 }, connect: vi.fn(), disconnect: vi.fn() };
  const analyser: any = { fftSize: 0, smoothingTimeConstant: 0, connect: vi.fn(), context: null };
  const scriptNode = { onaudioprocess: null, connect: vi.fn(), disconnect: vi.fn() };
  let release!: () => void;
  const ctx: any = {
    state: 'suspended',
    destination: {},
    resume: vi.fn(() => new Promise<void>((resolve) => { release = () => resolve(); })),
    createGain: vi.fn(() => gain),
    createAnalyser: vi.fn(() => analyser),
    createScriptProcessor: vi.fn(() => scriptNode),
    audioWorklet: undefined, // the synchronous ScriptProcessorNode fallback
  };
  analyser.context = ctx;
  return { ctx, release: () => release() };
}

function setup() {
  const store = configureStore({ reducer: { player: playerReducer } });
  const wrapper = ({ children }: { children: ReactNode }) => <Provider store={store}>{children}</Provider>;
  const hook = renderHook(() => useAudioStreamingCore(WS as never, OPTIONS), { wrapper });

  const buffer = new PCMStreamBuffer(PCMStreamBuffer.MAX_CAPACITY_BYTES);
  buffer.initialize(SAMPLE_RATE, CHANNELS);
  buffer.append(new Float32Array(10 * SAMPLE_RATE * CHANNELS));
  const { ctx, release } = suspendedContext();
  const engine = new AudioPlaybackEngine(ctx, buffer);

  const core = hook.result.current;
  core.pcmBufferRef.current = buffer;
  core.playbackEngineRef.current = engine;
  core.streamingMetadataRef.current = {
    sampleRate: SAMPLE_RATE, channels: CHANNELS, totalChunks: 1, processedChunks: 1,
  };
  return { hook, engine, ctx, release };
}

describe('pause inside the first-play start window (#6424)', () => {
  it('leaves the engine and the UI paused once the start would have completed', async () => {
    const { hook, engine, ctx, release } = setup();

    act(() => { hook.result.current.startPlaybackWhenBuffered(); }); // chunk landed: start parks on resume()
    act(() => { hook.result.current.pausePlayback(); }); // user clicks pause inside the window
    await act(async () => { release(); await Promise.resolve(); });

    expect(ctx.createScriptProcessor).not.toHaveBeenCalled();
    expect(engine.isPlaying()).toBe(false);
    expect(hook.result.current.isPaused).toBe(true);
    expect(hook.result.current.pauseHoldRef.current).toBe(true);
  });

  it('a chunk arriving while paused does not start playback (the hold still applies)', async () => {
    const { hook, engine, ctx, release } = setup();
    act(() => { hook.result.current.startPlaybackWhenBuffered(); });
    act(() => { hook.result.current.pausePlayback(); });
    await act(async () => { release(); await Promise.resolve(); });

    act(() => { hook.result.current.startPlaybackWhenBuffered(); });

    expect(engine.isPlaying()).toBe(false);
    expect(ctx.resume).toHaveBeenCalledTimes(1); // no second attempt was started
  });

  it('resume after that pause starts playback', async () => {
    const { hook, engine, ctx, release } = setup();
    act(() => { hook.result.current.startPlaybackWhenBuffered(); });
    act(() => { hook.result.current.pausePlayback(); });
    ctx.state = 'running'; // the context came up while the user was paused

    await act(async () => { hook.result.current.resumePlayback(); await Promise.resolve(); await Promise.resolve(); });

    expect(engine.isPlaying()).toBe(true);
    expect(hook.result.current.isPaused).toBe(false);

    await act(async () => { release(); await Promise.resolve(); }); // the cancelled attempt unwinds harmlessly
    expect(ctx.createScriptProcessor).toHaveBeenCalledOnce();
  });
});
