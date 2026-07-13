/**
 * AudioPlaybackEngine Tests (issue #3935 / TC-7)
 *
 * AudioPlaybackEngine had zero unit tests of its own logic — the only place
 * it appeared in the test suite was fully mocked out (usePlayEnhanced.test.ts,
 * usePlayNormal.test.ts). This suite imports the real class and a real
 * PCMStreamBuffer (a plain data structure with no browser dependencies), and
 * mocks only the Web Audio API surface (AudioContext/GainNode/AnalyserNode/
 * ScriptProcessorNode), forcing the AudioWorklet path off (`audioWorklet:
 * undefined`) so the synchronous ScriptProcessorNode fallback — real
 * production code, not a mock — is what's under test.
 */

import { describe, it, expect, vi, afterEach } from 'vitest';
import { AudioPlaybackEngine } from '../AudioPlaybackEngine';
import { PCMStreamBuffer } from '../PCMStreamBuffer';
import { PLAYBACK_ENGINE_CONFIG } from '../audioConstants';

const SAMPLE_RATE = 48000;
const CHANNELS = 2;

/** Minimal Web Audio node/context mocks — just enough surface for
 * AudioPlaybackEngine's constructor + ScriptProcessorNode fallback path. */
function createMockAudioContext() {
  const gainNode = { gain: { value: 1 }, connect: vi.fn(), disconnect: vi.fn() };
  const analyserNode: any = {
    fftSize: 0,
    smoothingTimeConstant: 0,
    connect: vi.fn(),
    context: null,
  };
  const scriptNode = {
    onaudioprocess: null as ((e: unknown) => void) | null,
    connect: vi.fn(),
    disconnect: vi.fn(),
  };

  const ctx: any = {
    state: 'running',
    destination: {},
    resume: vi.fn().mockResolvedValue(undefined),
    createGain: vi.fn(() => gainNode),
    createAnalyser: vi.fn(() => analyserNode),
    createScriptProcessor: vi.fn(() => scriptNode),
    // Force the synchronous ScriptProcessorNode fallback instead of the
    // async AudioWorklet path (initWorklet() checks this and returns false).
    audioWorklet: undefined,
  };
  analyserNode.context = ctx;

  return { ctx, gainNode, analyserNode, scriptNode };
}

/** A real, initialized PCMStreamBuffer with `seconds` worth of silence. */
function makeBuffer(seconds: number): PCMStreamBuffer {
  const buffer = new PCMStreamBuffer();
  buffer.initialize(SAMPLE_RATE, CHANNELS);
  const sampleCount = Math.floor(seconds * SAMPLE_RATE * CHANNELS);
  buffer.append(new Float32Array(sampleCount));
  return buffer;
}

/** Mock AudioProcessingEvent for driving scriptNode.onaudioprocess directly. */
function makeProcessEvent(frames: number, channels = CHANNELS) {
  const data: Float32Array[] = Array.from({ length: channels }, () => new Float32Array(frames));
  return {
    outputBuffer: {
      numberOfChannels: channels,
      length: frames,
      getChannelData: (ch: number) => data[ch],
    },
    _channelData: data,
  };
}

describe('AudioPlaybackEngine', () => {
  afterEach(() => {
    delete (window as any).__auralisAnalyser;
    delete (window as any).__auralisAudioContext;
  });

  it('connects gainNode -> analyser -> destination on construction', () => {
    const { ctx, gainNode, analyserNode } = createMockAudioContext();
    const buffer = makeBuffer(0.1);

    new AudioPlaybackEngine(ctx, buffer);

    expect(gainNode.connect).toHaveBeenCalledWith(analyserNode);
    expect(analyserNode.connect).toHaveBeenCalledWith(ctx.destination);
    expect(window.__auralisAudioContext).toBe(ctx);
  });

  it('disconnects the gainNode on dispose() so it is not stranded (#4445)', () => {
    const { ctx, gainNode } = createMockAudioContext();
    const engine = new AudioPlaybackEngine(ctx, makeBuffer(0.1));

    engine.dispose();

    // The permanently-wired gainNode must be released (disconnectProcessor never
    // touched it), otherwise enhanced-mode track switches strand one per switch.
    expect(gainNode.disconnect).toHaveBeenCalled();
  });

  it('dispose() is idempotent and swallows a disconnect throw (closed context) (#4445)', () => {
    const { ctx, gainNode } = createMockAudioContext();
    const engine = new AudioPlaybackEngine(ctx, makeBuffer(0.1));
    gainNode.disconnect.mockImplementationOnce(() => {
      throw new DOMException('context closed', 'InvalidStateError');
    });

    expect(() => {
      engine.dispose();
      engine.dispose();
    }).not.toThrow();
  });

  it('clamps volume to [0, 1]', () => {
    const { ctx, gainNode } = createMockAudioContext();
    const engine = new AudioPlaybackEngine(ctx, makeBuffer(0.1));

    engine.setVolume(1.5);
    expect(gainNode.gain.value).toBe(1);

    engine.setVolume(-0.5);
    expect(gainNode.gain.value).toBe(0);

    engine.setVolume(0.42);
    expect(gainNode.gain.value).toBeCloseTo(0.42);
  });

  describe('startPlayback', () => {
    it('sets error state and fires the underrun callback when the buffer has too few samples', async () => {
      const { ctx } = createMockAudioContext();
      const engine = new AudioPlaybackEngine(ctx, makeBuffer(0.01)); // far below minBufferSamples
      const onUnderrun = vi.fn();
      const onStateChange = vi.fn();
      engine.onUnderrun(onUnderrun);
      engine.onStateChanged(onStateChange);

      await engine.startPlayback();

      expect(onStateChange).toHaveBeenCalledWith('error');
      expect(onUnderrun).toHaveBeenCalledOnce();
      expect(engine.isPlaying()).toBe(false);
    });

    it('starts playback via the ScriptProcessorNode fallback when the buffer has enough samples', async () => {
      const { ctx, gainNode, scriptNode } = createMockAudioContext();
      // minBufferSamples (~1s @ 48kHz stereo) — use a healthy 10s buffer.
      const engine = new AudioPlaybackEngine(ctx, makeBuffer(10));
      const onStateChange = vi.fn();
      engine.onStateChanged(onStateChange);

      await engine.startPlayback();

      expect(ctx.createScriptProcessor).toHaveBeenCalledWith(
        PLAYBACK_ENGINE_CONFIG.bufferSize, 0, CHANNELS
      );
      expect(scriptNode.connect).toHaveBeenCalledWith(gainNode);
      expect(scriptNode.onaudioprocess).toBeTypeOf('function');
      expect(onStateChange).toHaveBeenCalledWith('playing');
      expect(engine.isPlaying()).toBe(true);
    });

    it('resumes a suspended AudioContext before starting playback', async () => {
      const { ctx } = createMockAudioContext();
      ctx.state = 'suspended';
      const engine = new AudioPlaybackEngine(ctx, makeBuffer(10));

      await engine.startPlayback();

      expect(ctx.resume).toHaveBeenCalledOnce();
      expect(engine.isPlaying()).toBe(true);
    });

    it('is a no-op when already playing', async () => {
      const { ctx } = createMockAudioContext();
      const engine = new AudioPlaybackEngine(ctx, makeBuffer(10));
      await engine.startPlayback();

      const callsBefore = ctx.createScriptProcessor.mock.calls.length;
      await engine.startPlayback();

      expect(ctx.createScriptProcessor.mock.calls.length).toBe(callsBefore);
    });
  });

  describe('pause / resume / stop', () => {
    it('pausePlayback disconnects the processor and transitions to paused', async () => {
      const { ctx, scriptNode } = createMockAudioContext();
      const engine = new AudioPlaybackEngine(ctx, makeBuffer(10));
      await engine.startPlayback();

      engine.pausePlayback();

      expect(scriptNode.disconnect).toHaveBeenCalledOnce();
      expect(engine.isPlaying()).toBe(false);
      expect(engine.getStats().isPlaying).toBe(false);
    });

    it('resumePlayback recreates the processor and transitions back to playing', async () => {
      const { ctx } = createMockAudioContext();
      const engine = new AudioPlaybackEngine(ctx, makeBuffer(10));
      await engine.startPlayback();
      engine.pausePlayback();

      engine.resumePlayback();

      expect(engine.isPlaying()).toBe(true);
    });

    it('stopPlayback resets timing state and transitions to stopped', async () => {
      const { ctx } = createMockAudioContext();
      const engine = new AudioPlaybackEngine(ctx, makeBuffer(10));
      await engine.startPlayback();

      engine.stopPlayback();

      expect(engine.isPlaying()).toBe(false);
      expect(engine.getCurrentPlaybackTime()).toBe(0);
      expect(engine.getStats().bufferUnderuns).toBe(0);
    });

    it('pausePlayback is a no-op when not playing', () => {
      const { ctx, scriptNode } = createMockAudioContext();
      const engine = new AudioPlaybackEngine(ctx, makeBuffer(10));

      engine.pausePlayback();

      expect(scriptNode.disconnect).not.toHaveBeenCalled();
    });
  });

  describe('getCurrentPlaybackTime / seek offset', () => {
    it('returns 0 when idle', () => {
      const { ctx } = createMockAudioContext();
      const engine = new AudioPlaybackEngine(ctx, makeBuffer(10));
      expect(engine.getCurrentPlaybackTime()).toBe(0);
    });

    it('honours setSeekOffset once playback starts', async () => {
      const { ctx } = createMockAudioContext();
      const engine = new AudioPlaybackEngine(ctx, makeBuffer(10));
      engine.setSeekOffset(30);

      await engine.startPlayback();

      // samplesPlayed is 0 immediately after start, so time == seek offset.
      expect(engine.getCurrentPlaybackTime()).toBe(30);
    });

    it('clamps a negative seek offset to 0', async () => {
      const { ctx } = createMockAudioContext();
      const engine = new AudioPlaybackEngine(ctx, makeBuffer(10));
      engine.setSeekOffset(-5);

      await engine.startPlayback();

      expect(engine.getCurrentPlaybackTime()).toBe(0);
    });

    it('holds the paused time while paused', async () => {
      const { ctx } = createMockAudioContext();
      const engine = new AudioPlaybackEngine(ctx, makeBuffer(10));
      engine.setSeekOffset(5);
      await engine.startPlayback();

      engine.pausePlayback();

      expect(engine.getCurrentPlaybackTime()).toBe(5);
    });
  });

  describe('onStateChanged / onUnderrun subscriptions', () => {
    it('unsubscribe stops further callback invocations', async () => {
      const { ctx } = createMockAudioContext();
      const engine = new AudioPlaybackEngine(ctx, makeBuffer(10));
      const onStateChange = vi.fn();
      const unsubscribe = engine.onStateChanged(onStateChange);

      await engine.startPlayback();
      expect(onStateChange).toHaveBeenCalledWith('playing');

      unsubscribe();
      onStateChange.mockClear();
      engine.pausePlayback();

      expect(onStateChange).not.toHaveBeenCalled();
    });
  });

  describe('ScriptProcessorNode audio callback (handleAudioProcess)', () => {
    it('outputs silence and does not advance samplesPlayed when the buffer is below the low water mark', async () => {
      const { ctx, scriptNode } = createMockAudioContext();
      // ~1s buffer: enough to pass startPlayback()'s minBufferSamples gate,
      // but below lowWaterMarkSeconds (5s) — handleAudioProcess should pause.
      const engine = new AudioPlaybackEngine(ctx, makeBuffer(1));
      await engine.startPlayback();

      const event = makeProcessEvent(1024);
      scriptNode.onaudioprocess!(event);

      expect(Array.from(event._channelData[0])).toEqual(new Array(1024).fill(0));
      expect(Array.from(event._channelData[1])).toEqual(new Array(1024).fill(0));
      expect(engine.getStats().samplesPlayed).toBe(0);
    });

    it('reads and de-interleaves stereo samples, advancing samplesPlayed by frame count', async () => {
      const { ctx, scriptNode } = createMockAudioContext();
      const buffer = new PCMStreamBuffer();
      buffer.initialize(SAMPLE_RATE, CHANNELS);
      // Well above the 5s low water mark so handleAudioProcess reads real data.
      const seconds = 10;
      const totalFrames = seconds * SAMPLE_RATE;
      const interleaved = new Float32Array(totalFrames * CHANNELS);
      for (let i = 0; i < totalFrames; i++) {
        interleaved[i * 2] = i;       // left channel: frame index
        interleaved[i * 2 + 1] = -i;  // right channel: negated frame index
      }
      buffer.append(interleaved);

      const engine = new AudioPlaybackEngine(ctx, buffer);
      await engine.startPlayback();

      const frames = 512;
      const event = makeProcessEvent(frames);
      scriptNode.onaudioprocess!(event);

      expect(event._channelData[0][0]).toBe(0);
      expect(event._channelData[1][0]).toBe(0);
      expect(event._channelData[0][10]).toBe(10);
      expect(event._channelData[1][10]).toBe(-10);
      expect(engine.getStats().samplesPlayed).toBe(frames);
    });
  });
});
