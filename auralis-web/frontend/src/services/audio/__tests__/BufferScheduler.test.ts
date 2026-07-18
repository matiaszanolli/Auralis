/**
 * BufferScheduler Tests (#4301)
 *
 * Isolated unit tests for the Web Audio worklet/script-processor feeding
 * logic extracted from AudioPlaybackEngine. Uses a real PCMStreamBuffer (a
 * plain data structure with no browser dependencies) and mocks only the
 * Web Audio API surface (AudioContext/GainNode/ScriptProcessorNode/
 * AudioWorkletNode).
 */

import { describe, it, expect, vi, afterEach } from 'vitest';
import { BufferScheduler, type BufferSchedulerCallbacks } from '../BufferScheduler';
import { PCMStreamBuffer } from '../PCMStreamBuffer';
import { PLAYBACK_ENGINE_CONFIG } from '../audioConstants';

const SAMPLE_RATE = 48000;
const CHANNELS = 2;

function makeBuffer(seconds: number, channels = CHANNELS): PCMStreamBuffer {
  const buffer = new PCMStreamBuffer();
  buffer.initialize(SAMPLE_RATE, channels);
  buffer.append(new Float32Array(Math.floor(seconds * SAMPLE_RATE * channels)));
  return buffer;
}

function makeCallbacks() {
  return {
    onSamplesPlayedSet: vi.fn(),
    onSamplesPlayedIncrement: vi.fn(),
    onUnderrun: vi.fn(),
  } satisfies BufferSchedulerCallbacks;
}

/** Context with no AudioWorklet support — forces the ScriptProcessorNode fallback. */
function createScriptOnlyContext() {
  const gainNode = { connect: vi.fn(), disconnect: vi.fn() };
  const scriptNode = {
    onaudioprocess: null as ((e: unknown) => void) | null,
    connect: vi.fn(),
    disconnect: vi.fn(),
  };
  const ctx: any = {
    createScriptProcessor: vi.fn(() => scriptNode),
    audioWorklet: undefined,
  };
  return { ctx, gainNode, scriptNode };
}

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

describe('BufferScheduler', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('getMinBufferSamples returns the configured constant', () => {
    const { ctx, gainNode } = createScriptOnlyContext();
    const scheduler = new BufferScheduler(ctx, makeBuffer(10), gainNode as any, makeCallbacks());
    expect(scheduler.getMinBufferSamples()).toBe(PLAYBACK_ENGINE_CONFIG.minBufferSamples);
  });

  describe('ScriptProcessorNode fallback', () => {
    it('ensureReady + createProcessor creates and connects a ScriptProcessorNode when no AudioWorklet is available', async () => {
      const { ctx, gainNode, scriptNode } = createScriptOnlyContext();
      const scheduler = new BufferScheduler(ctx, makeBuffer(10), gainNode as any, makeCallbacks());

      await scheduler.ensureReady();
      scheduler.createProcessor();

      expect(ctx.createScriptProcessor).toHaveBeenCalledWith(PLAYBACK_ENGINE_CONFIG.bufferSize, 0, CHANNELS);
      expect(scriptNode.connect).toHaveBeenCalledWith(gainNode);
      expect(scriptNode.onaudioprocess).toBeTypeOf('function');
    });

    it('createProcessor is idempotent — a second call does not recreate the node', async () => {
      const { ctx, gainNode } = createScriptOnlyContext();
      const scheduler = new BufferScheduler(ctx, makeBuffer(10), gainNode as any, makeCallbacks());
      await scheduler.ensureReady();

      scheduler.createProcessor();
      scheduler.createProcessor();

      expect(ctx.createScriptProcessor).toHaveBeenCalledTimes(1);
    });

    it('disconnectProcessor disconnects the node and clears it so createProcessor can recreate it', async () => {
      const { ctx, gainNode, scriptNode } = createScriptOnlyContext();
      const scheduler = new BufferScheduler(ctx, makeBuffer(10), gainNode as any, makeCallbacks());
      await scheduler.ensureReady();
      scheduler.createProcessor();

      scheduler.disconnectProcessor();
      scheduler.createProcessor();

      expect(scriptNode.disconnect).toHaveBeenCalledOnce();
      expect(ctx.createScriptProcessor).toHaveBeenCalledTimes(2);
    });

    describe('handleAudioProcess (via onaudioprocess)', () => {
      it('outputs silence and skips onSamplesPlayedIncrement below the low water mark', async () => {
        const { ctx, gainNode, scriptNode } = createScriptOnlyContext();
        const callbacks = makeCallbacks();
        // 1s buffer is below the 5s low water mark.
        const scheduler = new BufferScheduler(ctx, makeBuffer(1), gainNode as any, callbacks);
        await scheduler.ensureReady();
        scheduler.createProcessor();

        const event = makeProcessEvent(256);
        scriptNode.onaudioprocess!(event);

        expect(Array.from(event._channelData[0])).toEqual(new Array(256).fill(0));
        expect(callbacks.onSamplesPlayedIncrement).not.toHaveBeenCalled();
      });

      it('de-interleaves stereo samples and reports frame count via onSamplesPlayedIncrement', async () => {
        const { ctx, gainNode, scriptNode } = createScriptOnlyContext();
        const callbacks = makeCallbacks();
        const buffer = makeBuffer(10); // above the 5s low water mark
        const scheduler = new BufferScheduler(ctx, buffer, gainNode as any, callbacks);
        await scheduler.ensureReady();
        scheduler.createProcessor();

        const frames = 512;
        const event = makeProcessEvent(frames);
        scriptNode.onaudioprocess!(event);

        expect(callbacks.onSamplesPlayedIncrement).toHaveBeenCalledWith(frames);
      });

      it('copies mono samples to every output channel', async () => {
        const { ctx, gainNode, scriptNode } = createScriptOnlyContext();
        const callbacks = makeCallbacks();
        const buffer = new PCMStreamBuffer();
        buffer.initialize(SAMPLE_RATE, 1);
        const totalFrames = 10 * SAMPLE_RATE;
        const mono = new Float32Array(totalFrames);
        for (let i = 0; i < totalFrames; i++) mono[i] = i;
        buffer.append(mono);
        const scheduler = new BufferScheduler(ctx, buffer, gainNode as any, callbacks);
        await scheduler.ensureReady();
        scheduler.createProcessor();

        const event = makeProcessEvent(64, 2); // stereo output from a mono source
        scriptNode.onaudioprocess!(event);

        expect(event._channelData[0][5]).toBe(5);
        expect(event._channelData[1][5]).toBe(5);
      });

      it('reports an underrun when read() returns fewer samples than the health check expected', async () => {
        const { ctx, gainNode, scriptNode } = createScriptOnlyContext();
        const callbacks = makeCallbacks();
        // A buffer health check reads getAvailableSamples() (reports plenty,
        // clearing the low-water-mark gate) while read() itself returns
        // nothing — the defensive "shouldn't happen" race the underrun
        // branch guards against. Decoupling the two requires a fake buffer;
        // a real PCMStreamBuffer keeps them consistent by construction.
        const fakeBuffer: any = {
          getMetadata: () => ({ sampleRate: SAMPLE_RATE, channels: CHANNELS }),
          getAvailableSamples: () => SAMPLE_RATE * 10 * CHANNELS, // well above water marks
          read: () => new Float32Array(0),
        };
        const scheduler = new BufferScheduler(ctx, fakeBuffer, gainNode as any, callbacks);
        await scheduler.ensureReady();
        scheduler.createProcessor();

        scriptNode.onaudioprocess!(makeProcessEvent(256));

        expect(callbacks.onUnderrun).toHaveBeenCalledOnce();
        expect(scheduler.getUnderrunCount()).toBe(1);
      });
    });
  });

  describe('AudioWorkletNode path', () => {
    it('uses AudioWorkletNode when the worklet module loads successfully', async () => {
      const port = { postMessage: vi.fn(), onmessage: null as ((e: unknown) => void) | null };
      class MockAudioWorkletNode {
        port = port;
        connect = vi.fn();
        disconnect = vi.fn();
        constructor(_ctx: unknown, _name: string, _opts: unknown) {}
      }
      vi.stubGlobal('AudioWorkletNode', MockAudioWorkletNode);

      const gainNode = { connect: vi.fn(), disconnect: vi.fn() };
      const ctx: any = {
        audioWorklet: { addModule: vi.fn().mockResolvedValue(undefined) },
      };
      const callbacks = makeCallbacks();
      const scheduler = new BufferScheduler(ctx, makeBuffer(10), gainNode as any, callbacks);

      await scheduler.ensureReady();
      scheduler.createProcessor();

      expect(ctx.audioWorklet.addModule).toHaveBeenCalledWith('/audio-worklet-processor.js');
      expect(port.postMessage).toHaveBeenCalledWith({ command: 'setChannels', channels: CHANNELS });

      // Worklet reports samplesPlayed as an absolute count.
      port.onmessage!({ data: { type: 'samplesPlayed', count: 999 } } as MessageEvent);
      expect(callbacks.onSamplesPlayedSet).toHaveBeenCalledWith(999);

      port.onmessage!({ data: { type: 'underrun' } } as MessageEvent);
      expect(callbacks.onUnderrun).toHaveBeenCalledOnce();
      expect(scheduler.getUnderrunCount()).toBe(1);
    });

    it('falls back to ScriptProcessorNode when audioWorklet.addModule rejects', async () => {
      const { scriptNode } = (() => {
        const scriptNode = { onaudioprocess: null, connect: vi.fn(), disconnect: vi.fn() };
        return { scriptNode };
      })();
      const gainNode = { connect: vi.fn(), disconnect: vi.fn() };
      const ctx: any = {
        audioWorklet: { addModule: vi.fn().mockRejectedValue(new Error('no worklet support')) },
        createScriptProcessor: vi.fn(() => scriptNode),
      };
      const callbacks = makeCallbacks();
      const scheduler = new BufferScheduler(ctx, makeBuffer(10), gainNode as any, callbacks);

      await scheduler.ensureReady();
      scheduler.createProcessor();

      expect(ctx.createScriptProcessor).toHaveBeenCalled();
    });
  });

  describe('resetUnderrunCount / resetBufferHealth', () => {
    it('resetUnderrunCount zeroes getUnderrunCount', async () => {
      const { ctx, gainNode, scriptNode } = createScriptOnlyContext();
      const callbacks = makeCallbacks();
      const fakeBuffer: any = {
        getMetadata: () => ({ sampleRate: SAMPLE_RATE, channels: CHANNELS }),
        getAvailableSamples: () => SAMPLE_RATE * 10 * CHANNELS,
        read: () => new Float32Array(0),
      };
      const scheduler = new BufferScheduler(ctx, fakeBuffer, gainNode as any, callbacks);
      await scheduler.ensureReady();
      scheduler.createProcessor();
      scriptNode.onaudioprocess!(makeProcessEvent(256)); // underruns

      expect(scheduler.getUnderrunCount()).toBeGreaterThan(0);
      scheduler.resetUnderrunCount();
      expect(scheduler.getUnderrunCount()).toBe(0);
    });

    it('resetBufferHealth allows a subsequent low-buffer pause to log again (no throw)', () => {
      const { ctx, gainNode } = createScriptOnlyContext();
      const scheduler = new BufferScheduler(ctx, makeBuffer(1), gainNode as any, makeCallbacks());
      expect(() => scheduler.resetBufferHealth()).not.toThrow();
    });
  });
});
