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
  const buffer = new PCMStreamBuffer(PCMStreamBuffer.MAX_CAPACITY_BYTES);
  buffer.initialize(SAMPLE_RATE, channels);
  buffer.append(new Float32Array(Math.floor(seconds * SAMPLE_RATE * channels)));
  return buffer;
}

function makeCallbacks() {
  return {
    onSamplesPlayedSet: vi.fn(),
    onSamplesPlayedIncrement: vi.fn(),
    onUnderrun: vi.fn(),
    onStallChange: vi.fn(),
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
        const buffer = new PCMStreamBuffer(PCMStreamBuffer.MAX_CAPACITY_BYTES);
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

  describe('stall reporting (#5461)', () => {
    function emptyThenFlowingBuffer() {
      const state = { empty: true };
      const buffer: any = {
        getMetadata: () => ({ sampleRate: SAMPLE_RATE, channels: CHANNELS }),
        getAvailableSamples: () => SAMPLE_RATE * 10 * CHANNELS, // above both water marks
        read: (n: number) => (state.empty ? new Float32Array(0) : new Float32Array(n)),
      };
      return { buffer, state };
    }

    it('reports a low-water pause once, then its recovery once', async () => {
      const { ctx, gainNode, scriptNode } = createScriptOnlyContext();
      const callbacks = makeCallbacks();
      const buffer = makeBuffer(1); // below the 5 s low-water mark
      const scheduler = new BufferScheduler(ctx, buffer, gainNode as any, callbacks);
      await scheduler.ensureReady();
      scheduler.createProcessor();

      scriptNode.onaudioprocess!(makeProcessEvent(256));
      scriptNode.onaudioprocess!(makeProcessEvent(256));
      expect(callbacks.onStallChange.mock.calls).toEqual([[true]]);

      buffer.append(new Float32Array(10 * SAMPLE_RATE * CHANNELS)); // past the 8 s high-water mark
      scriptNode.onaudioprocess!(makeProcessEvent(256));
      expect(callbacks.onStallChange.mock.calls).toEqual([[true], [false]]);
    });

    it('treats a hard underrun as a stall until audio flows again', async () => {
      const { ctx, gainNode, scriptNode } = createScriptOnlyContext();
      const callbacks = makeCallbacks();
      const { buffer, state } = emptyThenFlowingBuffer();
      const scheduler = new BufferScheduler(ctx, buffer, gainNode as any, callbacks);
      await scheduler.ensureReady();
      scheduler.createProcessor();

      scriptNode.onaudioprocess!(makeProcessEvent(256));
      scriptNode.onaudioprocess!(makeProcessEvent(256));
      expect(callbacks.onStallChange.mock.calls).toEqual([[true]]);

      state.empty = false;
      scriptNode.onaudioprocess!(makeProcessEvent(256));
      expect(callbacks.onStallChange.mock.calls).toEqual([[true], [false]]);
    });

    it('worklet: an underrun stalls and the next progress report recovers', async () => {
      const port = { postMessage: vi.fn(), onmessage: null as ((e: unknown) => void) | null };
      class MockAudioWorkletNode {
        port = port;
        connect = vi.fn();
        disconnect = vi.fn();
        constructor(_ctx: unknown, _name: string, _opts: unknown) {}
      }
      vi.stubGlobal('AudioWorkletNode', MockAudioWorkletNode);
      const ctx: any = { audioWorklet: { addModule: vi.fn().mockResolvedValue(undefined) } };
      const callbacks = makeCallbacks();
      const scheduler = new BufferScheduler(
        ctx, makeBuffer(10), { connect: vi.fn(), disconnect: vi.fn() } as any, callbacks
      );
      await scheduler.ensureReady();
      scheduler.createProcessor();

      port.onmessage!({ data: { type: 'underrun' } } as MessageEvent);
      port.onmessage!({ data: { type: 'underrun' } } as MessageEvent);
      expect(callbacks.onStallChange.mock.calls).toEqual([[true]]);

      port.onmessage!({ data: { type: 'samplesPlayed', count: 4096 } } as MessageEvent);
      expect(callbacks.onStallChange.mock.calls).toEqual([[true], [false]]);
      scheduler.disconnectProcessor();
    });

    it('resetBufferHealth reports recovery from a stall', async () => {
      const { ctx, gainNode, scriptNode } = createScriptOnlyContext();
      const callbacks = makeCallbacks();
      const { buffer } = emptyThenFlowingBuffer();
      const scheduler = new BufferScheduler(ctx, buffer, gainNode as any, callbacks);
      await scheduler.ensureReady();
      scheduler.createProcessor();
      scriptNode.onaudioprocess!(makeProcessEvent(256));

      scheduler.resetBufferHealth();

      expect(callbacks.onStallChange.mock.calls).toEqual([[true], [false]]);
    });
  });
  describe('worklet lookahead and pause (#5657)', () => {
    const FEED_MS = PLAYBACK_ENGINE_CONFIG.feedIntervalMs;
    const LOOKAHEAD_FRAMES = PLAYBACK_ENGINE_CONFIG.workletLookaheadSeconds * SAMPLE_RATE;
    const MAX_FEED = PLAYBACK_ENGINE_CONFIG.maxFeedFramesPerTick;

    afterEach(() => {
      vi.useRealTimers();
    });

    async function makeWorkletScheduler(ringSeconds: number) {
      vi.useFakeTimers();
      const port = { postMessage: vi.fn(), onmessage: null as ((e: unknown) => void) | null };
      const created = vi.fn();
      class MockAudioWorkletNode {
        port = port;
        connect = vi.fn();
        disconnect = vi.fn();
        constructor(_ctx: unknown, _name: string, _opts: unknown) {
          created();
        }
      }
      vi.stubGlobal('AudioWorkletNode', MockAudioWorkletNode);
      const ctx: any = { audioWorklet: { addModule: vi.fn().mockResolvedValue(undefined) } };
      const callbacks = makeCallbacks();
      const scheduler = new BufferScheduler(
        ctx, makeBuffer(ringSeconds), { connect: vi.fn(), disconnect: vi.fn() } as any, callbacks
      );
      await scheduler.ensureReady();
      scheduler.createProcessor();

      /** Frames posted to the worklet so far. */
      const framesSent = () =>
        port.postMessage.mock.calls.reduce(
          (sum, [msg]) => sum + (msg.samples ? msg.samples.length / CHANNELS : 0), 0
        );
      const commands = () =>
        port.postMessage.mock.calls.map(([msg]) => msg.command).filter(Boolean);
      const report = (count: number) =>
        port.onmessage!({ data: { type: 'samplesPlayed', count, available: 0 } } as MessageEvent);
      return { scheduler, port, callbacks, created, framesSent, commands, report };
    }

    it('stops feeding once the worklet holds the target lookahead, however full the ring is', async () => {
      const { framesSent } = await makeWorkletScheduler(120);

      // 20 s of ticks with the worklet reporting nothing played. The old feeder
      // kept pushing 4096 frames per tick (~37 s of audio in these 20 s).
      await vi.advanceTimersByTimeAsync(20_000);

      expect(framesSent()).toBeGreaterThanOrEqual(LOOKAHEAD_FRAMES - MAX_FEED);
      expect(framesSent()).toBeLessThanOrEqual(LOOKAHEAD_FRAMES);
    });

    // #5665: blocks are transferred, not structured-cloned — the worklet was
    // paying a second full copy of every block, twice per feed.
    it('sends each block with its ArrayBuffer in a transfer list', async () => {
      const { port } = await makeWorkletScheduler(120);

      await vi.advanceTimersByTimeAsync(200);

      const samplePosts = port.postMessage.mock.calls.filter(([msg]) => msg.samples);
      expect(samplePosts.length).toBeGreaterThan(0);
      for (const [msg, transfer] of samplePosts) {
        expect(transfer).toEqual([msg.samples.buffer]);
      }
    });

    it('feeds only what the worklet has played since (a real-time consumer stays at the lookahead)', async () => {
      const { framesSent, report } = await makeWorkletScheduler(120);
      const framesPerTick = Math.round((SAMPLE_RATE * FEED_MS) / 1000);

      let played = 0;
      let maxQueued = 0;
      // 30 s of real-time playback; the worklet reports every 16384 frames.
      for (let tick = 0; tick < (30_000 / FEED_MS); tick++) {
        await vi.advanceTimersByTimeAsync(FEED_MS);
        const before = Math.floor(played / 16384);
        played = Math.min(played + framesPerTick, framesSent());
        if (Math.floor(played / 16384) > before) report(Math.floor(played / 16384) * 16384);
        maxQueued = Math.max(maxQueued, framesSent() - played);
      }

      // Never more than the lookahead (+ one tick of slack for the stale count)...
      expect(maxQueued).toBeLessThanOrEqual(LOOKAHEAD_FRAMES + MAX_FEED);
      // ...and total traffic tracks playback, not 1.8x of it.
      expect(framesSent()).toBeLessThanOrEqual(30 * SAMPLE_RATE + LOOKAHEAD_FRAMES + MAX_FEED);
      expect(framesSent()).toBeGreaterThan(30 * SAMPLE_RATE * 0.95);
    });

    it('counts audio queued in the worklet toward the water marks, not just the ring', async () => {
      // 6 s in the ring: once 3 s move into the worklet the ring alone (3 s) is
      // under the 5 s low-water mark, but 6 s are still buffered in total.
      const { framesSent, callbacks } = await makeWorkletScheduler(6);

      await vi.advanceTimersByTimeAsync(2_000);

      expect(framesSent()).toBeGreaterThanOrEqual(LOOKAHEAD_FRAMES - MAX_FEED);
      expect(callbacks.onStallChange).not.toHaveBeenCalled();
    });

    it('a low-water pause stops feeding but does not claim a stall while the worklet still plays', async () => {
      const { framesSent, callbacks, port } = await makeWorkletScheduler(1); // < 5 s: below low water

      await vi.advanceTimersByTimeAsync(1_000);
      expect(framesSent()).toBe(0);
      expect(callbacks.onStallChange).not.toHaveBeenCalled();

      // The stall is real once the worklet itself runs dry.
      port.onmessage!({ data: { type: 'underrun' } } as MessageEvent);
      expect(callbacks.onStallChange.mock.calls).toEqual([[true]]);
    });

    it('pauseOutput holds the worklet: no clear, no new node, feeding stops', async () => {
      const { scheduler, port, created, framesSent, commands } = await makeWorkletScheduler(120);
      await vi.advanceTimersByTimeAsync(500);
      const sentBeforePause = framesSent();

      scheduler.pauseOutput();
      await vi.advanceTimersByTimeAsync(5_000);

      expect(commands()).toContain('pause');
      expect(commands()).not.toContain('clear');
      expect(framesSent()).toBe(sentBeforePause);
      expect(created).toHaveBeenCalledOnce();
      expect(port.postMessage).not.toHaveBeenCalledWith({ command: 'clear' });
    });

    it('resumeOutput continues on the same worklet and feeds again', async () => {
      const { scheduler, created, framesSent, commands, report } = await makeWorkletScheduler(120);
      await vi.advanceTimersByTimeAsync(500);
      scheduler.pauseOutput();
      const sentWhilePaused = framesSent();

      scheduler.resumeOutput();
      report(48_000); // 1 s played -> credit for another second
      await vi.advanceTimersByTimeAsync(500);

      expect(commands().filter((c) => c === 'resume')).toHaveLength(1);
      expect(created).toHaveBeenCalledOnce();
      expect(framesSent()).toBeGreaterThan(sentWhilePaused);
    });

    it('createProcessor on a held worklet resumes it instead of leaving it paused', async () => {
      const { scheduler, commands } = await makeWorkletScheduler(120);
      scheduler.pauseOutput();

      scheduler.createProcessor();

      expect(commands()).toContain('resume');
    });

    it('disconnectProcessor (stop / seek) still discards the queue', async () => {
      const { scheduler, port } = await makeWorkletScheduler(120);

      scheduler.disconnectProcessor();

      expect(port.postMessage).toHaveBeenCalledWith({ command: 'clear' });
    });

    it('a new worklet starts its lookahead accounting from zero', async () => {
      const { scheduler, framesSent, report } = await makeWorkletScheduler(120);
      await vi.advanceTimersByTimeAsync(500);
      report(40_000);
      scheduler.disconnectProcessor();
      const sentBefore = framesSent();

      scheduler.createProcessor();
      await vi.advanceTimersByTimeAsync(500);

      // Stale sent/played counts from the old node must not starve the new one.
      expect(framesSent() - sentBefore).toBeGreaterThanOrEqual(LOOKAHEAD_FRAMES - MAX_FEED);
    });

    it('pauseOutput on the ScriptProcessor fallback disconnects it, resumeOutput recreates it', async () => {
      const { ctx, gainNode, scriptNode } = createScriptOnlyContext();
      const scheduler = new BufferScheduler(ctx, makeBuffer(10), gainNode as any, makeCallbacks());
      await scheduler.ensureReady();
      scheduler.createProcessor();

      scheduler.pauseOutput();
      expect(scriptNode.disconnect).toHaveBeenCalledOnce();

      scheduler.resumeOutput();
      expect(ctx.createScriptProcessor).toHaveBeenCalledTimes(2);
    });
  });
  describe('end of stream (tail of the track)', () => {
    afterEach(() => {
      vi.useRealTimers();
    });

    it('script path: holds output below the low-water mark until the stream is marked ended', async () => {
      const { ctx, gainNode, scriptNode } = createScriptOnlyContext();
      const callbacks = makeCallbacks();
      // 2 s left in the ring: under the 5 s low-water mark, and nothing more is coming.
      const scheduler = new BufferScheduler(ctx, makeBuffer(2), gainNode as any, callbacks);
      await scheduler.ensureReady();
      scheduler.createProcessor();

      scriptNode.onaudioprocess!(makeProcessEvent(256));
      expect(callbacks.onSamplesPlayedIncrement).not.toHaveBeenCalled(); // stranded

      scheduler.markStreamEnded();
      scriptNode.onaudioprocess!(makeProcessEvent(256));

      expect(callbacks.onSamplesPlayedIncrement).toHaveBeenCalledWith(256);
    });

    it('script path: plays the whole tail down to the last sample', async () => {
      const { ctx, gainNode, scriptNode } = createScriptOnlyContext();
      const callbacks = makeCallbacks();
      const scheduler = new BufferScheduler(ctx, makeBuffer(1), gainNode as any, callbacks);
      await scheduler.ensureReady();
      scheduler.createProcessor();
      scheduler.markStreamEnded();

      for (let i = 0; i < SAMPLE_RATE / 256 + 4; i++) scriptNode.onaudioprocess!(makeProcessEvent(256));

      const played = callbacks.onSamplesPlayedIncrement.mock.calls.reduce((n, [d]) => n + d, 0);
      expect(played).toBe(SAMPLE_RATE); // 1 s, not stranded at the 5 s mark
    });

    it('worklet path: keeps feeding the tail after the stream ends', async () => {
      vi.useFakeTimers();
      const port = { postMessage: vi.fn(), onmessage: null as ((e: unknown) => void) | null };
      class MockAudioWorkletNode {
        port = port;
        connect = vi.fn();
        disconnect = vi.fn();
        constructor(_ctx: unknown, _name: string, _opts: unknown) {}
      }
      vi.stubGlobal('AudioWorkletNode', MockAudioWorkletNode);
      const ctx: any = { audioWorklet: { addModule: vi.fn().mockResolvedValue(undefined) } };
      const scheduler = new BufferScheduler(
        ctx, makeBuffer(2), { connect: vi.fn(), disconnect: vi.fn() } as any, makeCallbacks()
      );
      await scheduler.ensureReady();
      scheduler.createProcessor();
      const sent = () =>
        port.postMessage.mock.calls.reduce(
          (n, [m]) => n + (m.samples ? m.samples.length / CHANNELS : 0), 0
        );

      await vi.advanceTimersByTimeAsync(1_000);
      expect(sent()).toBe(0); // 2 s < 5 s low-water: nothing is ever fed

      scheduler.markStreamEnded();
      await vi.advanceTimersByTimeAsync(1_000);

      expect(sent()).toBe(2 * SAMPLE_RATE); // the entire tail
    });

    it('resetStreamEnded restores the water-mark gating for the next stream', async () => {
      const { ctx, gainNode, scriptNode } = createScriptOnlyContext();
      const callbacks = makeCallbacks();
      const scheduler = new BufferScheduler(ctx, makeBuffer(2), gainNode as any, callbacks);
      await scheduler.ensureReady();
      scheduler.createProcessor();
      scheduler.markStreamEnded();

      scheduler.resetStreamEnded();
      scriptNode.onaudioprocess!(makeProcessEvent(256));

      expect(callbacks.onSamplesPlayedIncrement).not.toHaveBeenCalled();
    });
  });
});
