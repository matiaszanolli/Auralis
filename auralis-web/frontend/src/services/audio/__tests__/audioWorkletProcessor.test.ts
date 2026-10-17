/**
 * audio-worklet-processor.js — pause / resume / clear semantics (#5657)
 *
 * The processor lives in public/ as a plain script that registers itself with
 * the AudioWorkletGlobalScope. Here the real file is evaluated against a stub
 * of that scope, so the queue, played count and pause behaviour that the main
 * thread's BufferScheduler relies on are exercised for real.
 */

import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { beforeEach, describe, expect, it, vi } from 'vitest';

type Message = { type: string; count?: number; available?: number };

interface Processor {
  port: { postMessage: ReturnType<typeof vi.fn>; onmessage: ((e: { data: unknown }) => void) | null };
  process(inputs: unknown[], outputs: Float32Array[][]): boolean;
}

// vitest runs with the frontend package as cwd (import.meta.url is not a file:
// URL under jsdom).
const SOURCE = readFileSync(resolve(process.cwd(), 'public/audio-worklet-processor.js'), 'utf8');

function loadProcessor(): Processor {
  let Registered: (new () => Processor) | undefined;
  class AudioWorkletProcessor {
    port = { postMessage: vi.fn(), onmessage: null as ((e: { data: unknown }) => void) | null };
  }
  new Function('AudioWorkletProcessor', 'registerProcessor', SOURCE)(
    AudioWorkletProcessor,
    (_name: string, ctor: new () => Processor) => { Registered = ctor; },
  );
  return new Registered!();
}

const FRAMES = 128;
const send = (p: Processor, data: unknown) => p.port.onmessage!({ data });
const messages = (p: Processor): Message[] => p.port.postMessage.mock.calls.map(([m]) => m);

/** Interleaved stereo ramp 0,1,2,... so the sample at frame n is n (both channels). */
function ramp(startFrame: number, frames: number): Float32Array {
  const out = new Float32Array(frames * 2);
  for (let i = 0; i < frames; i++) out[i * 2] = out[i * 2 + 1] = startFrame + i;
  return out;
}

function render(p: Processor): { left: Float32Array; processed: boolean } {
  const left = new Float32Array(FRAMES).fill(-1);
  const right = new Float32Array(FRAMES).fill(-1);
  const processed = p.process([], [[left, right]]);
  return { left, processed };
}

describe('audio-worklet-processor (#5657)', () => {
  let p: Processor;

  beforeEach(() => {
    p = loadProcessor();
    send(p, { command: 'setChannels', channels: 2 });
  });

  it('plays queued PCM in order', () => {
    send(p, { samples: ramp(0, FRAMES * 2) });

    expect(render(p).left[0]).toBe(0);
    expect(render(p).left[0]).toBe(FRAMES);
  });

  it('pause outputs silence, keeps the queue, and consumes and counts nothing', () => {
    send(p, { samples: ramp(0, FRAMES * 4) });
    render(p); // frames 0..127 played

    send(p, { command: 'pause' });
    const held = render(p);
    render(p);

    expect(held.processed).toBe(true); // the node stays alive
    expect(Array.from(held.left)).toEqual(new Array(FRAMES).fill(0));
    // Paused is not an underrun, and playback is not counted.
    expect(messages(p).some((m) => m.type === 'underrun')).toBe(false);

    send(p, { command: 'resume' });
    expect(render(p).left[0]).toBe(FRAMES); // exactly where it left off
  });

  it('reports the exact played count and queue on pause', () => {
    send(p, { samples: ramp(0, FRAMES * 4) });
    render(p);
    render(p);
    p.port.postMessage.mockClear();

    send(p, { command: 'pause' });

    expect(messages(p)).toEqual([
      { type: 'samplesPlayed', count: FRAMES * 2, available: FRAMES * 2 * 2 },
    ]);
  });

  it('keeps counting from where it paused after resume (the count is never reset)', () => {
    send(p, { samples: ramp(0, FRAMES * 4) });
    render(p);
    send(p, { command: 'pause' });
    send(p, { command: 'resume' });
    p.port.postMessage.mockClear();
    send(p, { command: 'pause' });

    expect(messages(p)[0].count).toBe(FRAMES);
  });

  it('accepts and queues new PCM while paused', () => {
    send(p, { command: 'pause' });
    send(p, { samples: ramp(0, FRAMES) });
    send(p, { command: 'resume' });

    expect(render(p).left[0]).toBe(0);
  });

  it('clear discards the queue (stop / seek) so the next render underruns', () => {
    send(p, { samples: ramp(0, FRAMES * 4) });
    send(p, { command: 'clear' });
    p.port.postMessage.mockClear();

    render(p);

    expect(messages(p)).toEqual([{ type: 'underrun' }]);
  });

  it('an empty queue still underruns when not paused', () => {
    render(p);

    expect(messages(p)).toEqual([{ type: 'underrun' }]);
  });

  it('stop ends the processor', () => {
    send(p, { command: 'stop' });

    expect(render(p).processed).toBe(false);
  });
  it('reports its exact position as the queue runs dry, once per starvation', () => {
    send(p, { samples: ramp(0, FRAMES * 2) });
    render(p);
    render(p);
    p.port.postMessage.mockClear();

    render(p); // queue empty
    render(p);
    render(p);

    const samplesPlayed = messages(p).filter((m) => m.type === 'samplesPlayed');
    expect(samplesPlayed).toEqual([{ type: 'samplesPlayed', count: FRAMES * 2, available: 0 }]);
    // #5665: one underrun per stall, not one per render quantum.
    expect(messages(p).filter((m) => m.type === 'underrun')).toHaveLength(1);
  });

  it('posts one underrun per stall and again only after recovery (#5665)', () => {
    // A sustained stall of 100 render quanta posts exactly one message.
    for (let i = 0; i < 100; i++) render(p);
    expect(messages(p).filter((m) => m.type === 'underrun')).toHaveLength(1);

    // Audio is produced again, clearing the starved state...
    send(p, { samples: ramp(0, FRAMES) });
    render(p);
    p.port.postMessage.mockClear();

    // ...so a second stall posts again.
    for (let i = 0; i < 10; i++) render(p);
    expect(messages(p).filter((m) => m.type === 'underrun')).toHaveLength(1);
  });

  it('reports again when it runs dry a second time', () => {
    send(p, { samples: ramp(0, FRAMES) });
    render(p);
    render(p); // dry -> report
    send(p, { samples: ramp(0, FRAMES) });
    render(p);
    p.port.postMessage.mockClear();

    render(p); // dry again

    expect(messages(p).filter((m) => m.type === 'samplesPlayed')).toHaveLength(1);
  });

  it('sends no position report for an underrun before anything has played', () => {
    render(p);

    expect(messages(p)).toEqual([{ type: 'underrun' }]);
  });
});
