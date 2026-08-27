/**
 * Audio chunk ingest (#5041)
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * These behaviours used to live inside useAudioStreamingCore's 144-line
 * `handleChunk`, which meant the hottest path in the streaming client could
 * only be exercised by mounting React. Everything below runs against plain
 * functions and a fake buffer — no `renderHook`, no store, no WebSocket.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

import {
  FLOW_PAUSE_FILL_PCT,
  FLOW_RESUME_FILL_PCT,
  classifyChunk,
  ingestChunk,
  isOutOfSequence,
  nextFlowControlSignal,
  shouldDispatchProgress,
} from '../audioChunkIngest';
import type { StreamingMetadata } from '../useAudioStreamingCore';
import type { AudioChunkMessage } from '@/contexts/WebSocketContext';

vi.mock('@/utils/audio/pcmDecoding', () => ({
  decodeAudioChunkMessage: vi.fn(),
}));

import { decodeAudioChunkMessage } from '@/utils/audio/pcmDecoding';

const mockDecode = vi.mocked(decodeAudioChunkMessage);

function chunk(data: Partial<AudioChunkMessage['data']> = {}): AudioChunkMessage {
  return {
    type: 'audio_chunk',
    data: {
      chunk_index: 0,
      sample_count: 128,
      samples: '',
      ...data,
    },
  } as unknown as AudioChunkMessage;
}

function fakeBuffer(overrides: { fillPct?: number; available?: number } = {}) {
  return {
    append: vi.fn(),
    getFillPercentage: vi.fn(() => overrides.fillPct ?? 10),
    getAvailableSamples: vi.fn(() => overrides.available ?? 4410),
    reset: vi.fn(),
    dispose: vi.fn(),
  };
}

function meta(overrides: Partial<StreamingMetadata> = {}): StreamingMetadata {
  return {
    sampleRate: 44100,
    channels: 2,
    totalChunks: 10,
    processedChunks: 0,
    ...overrides,
  } as StreamingMetadata;
}

const acceptAll = () => true;

describe('classifyChunk', () => {
  it('rejects a chunk belonging to another stream type (#2104)', () => {
    expect(
      classifyChunk({
        message: chunk({ stream_type: 'normal' }),
        currentEpoch: null,
        initialized: true,
        acceptsStreamType: () => false,
      })
    ).toBe('wrong-stream-type');
  });

  it('drops a chunk from a superseded stream epoch (#4563)', () => {
    expect(
      classifyChunk({
        message: chunk({ stream_epoch: 1 }),
        currentEpoch: 2,
        initialized: true,
        acceptsStreamType: acceptAll,
      })
    ).toBe('superseded-epoch');
  });

  it('keeps a chunk whose epoch matches', () => {
    expect(
      classifyChunk({
        message: chunk({ stream_epoch: 2 }),
        currentEpoch: 2,
        initialized: true,
        acceptsStreamType: acceptAll,
      })
    ).toBeNull();
  });

  it('degrades gracefully when either side has no epoch', () => {
    // A backend that does not send stream_epoch must not have everything dropped.
    expect(
      classifyChunk({
        message: chunk({}),
        currentEpoch: 7,
        initialized: true,
        acceptsStreamType: acceptAll,
      })
    ).toBeNull();

    expect(
      classifyChunk({
        message: chunk({ stream_epoch: 7 }),
        currentEpoch: null,
        initialized: true,
        acceptsStreamType: acceptAll,
      })
    ).toBeNull();
  });

  it('reports not-initialized so the caller queues rather than drops', () => {
    expect(
      classifyChunk({
        message: chunk(),
        currentEpoch: null,
        initialized: false,
        acceptsStreamType: acceptAll,
      })
    ).toBe('not-initialized');
  });

  it('checks stream type before epoch', () => {
    // A foreign stream's epoch is meaningless, so type must win.
    expect(
      classifyChunk({
        message: chunk({ stream_epoch: 1 }),
        currentEpoch: 2,
        initialized: false,
        acceptsStreamType: () => false,
      })
    ).toBe('wrong-stream-type');
  });
});

describe('isOutOfSequence', () => {
  it('is false before any chunk has been seen', () => {
    expect(isOutOfSequence(-1, 0)).toBe(false);
    expect(isOutOfSequence(-1, 500)).toBe(false);
  });

  it('is false for forward progress and for a single-step retreat', () => {
    expect(isOutOfSequence(5, 6)).toBe(false);
    expect(isOutOfSequence(5, 5)).toBe(false);
    // 4 == last - 1: tolerated, a duplicate/adjacent resend is not a restart.
    expect(isOutOfSequence(5, 4)).toBe(false);
  });

  it('is true for a backwards jump of more than one', () => {
    expect(isOutOfSequence(5, 3)).toBe(true);
    expect(isOutOfSequence(50, 0)).toBe(true);
  });
});

describe('nextFlowControlSignal', () => {
  it('pauses only once, above the high-water mark', () => {
    expect(nextFlowControlSignal(FLOW_PAUSE_FILL_PCT + 1, false)).toBe('pause');
    expect(nextFlowControlSignal(FLOW_PAUSE_FILL_PCT + 1, true)).toBeNull();
  });

  it('resumes only once, below the low-water mark', () => {
    expect(nextFlowControlSignal(FLOW_RESUME_FILL_PCT - 1, true)).toBe('resume');
    expect(nextFlowControlSignal(FLOW_RESUME_FILL_PCT - 1, false)).toBeNull();
  });

  it('does nothing inside the hysteresis band', () => {
    // The gap between the marks is what stops the two frames ping-ponging.
    for (const fill of [FLOW_RESUME_FILL_PCT, 60, FLOW_PAUSE_FILL_PCT]) {
      expect(nextFlowControlSignal(fill, false)).toBeNull();
      expect(nextFlowControlSignal(fill, true)).toBeNull();
    }
  });
});

describe('shouldDispatchProgress', () => {
  it('dispatches every chunk when throttling is off', () => {
    expect(shouldDispatchProgress(1, 0, false)).toBe(true);
    expect(shouldDispatchProgress(1.5, 1.4, false)).toBe(true);
  });

  it('always dispatches the first update', () => {
    expect(shouldDispatchProgress(0, -1, true)).toBe(true);
  });

  it('dispatches on each decile crossing and suppresses within one', () => {
    expect(shouldDispatchProgress(11, 9, true)).toBe(true);
    expect(shouldDispatchProgress(19, 11, true)).toBe(false);
  });

  it('always dispatches completion', () => {
    expect(shouldDispatchProgress(100, 99, true)).toBe(true);
  });
});

describe('ingestChunk', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockDecode.mockReturnValue({
      samples: new Float32Array(128),
      metadata: { chunkIndex: 0, frameIndex: 0, frameCount: 1, sampleCount: 128 },
    } as ReturnType<typeof decodeAudioChunkMessage>);
  });

  it('decodes with the stream sample rate and channels, then appends', () => {
    const buffer = fakeBuffer();
    const m = meta({ sampleRate: 48000, channels: 1 });

    ingestChunk({ message: chunk(), buffer: buffer as never, metadata: m, flowPaused: false });

    expect(mockDecode).toHaveBeenCalledWith(expect.anything(), 48000, 1);
    expect(buffer.append).toHaveBeenCalledTimes(1);
  });

  it('counts one content chunk per final frame, not per message (#4414)', () => {
    const buffer = fakeBuffer();
    const m = meta({ totalChunks: 10 });

    // Three sub-frames of one content chunk: only the last advances the count.
    for (const frameIndex of [0, 1, 2]) {
      mockDecode.mockReturnValueOnce({
        samples: new Float32Array(128),
        metadata: { chunkIndex: 0, frameIndex, frameCount: 3, sampleCount: 128 },
      } as ReturnType<typeof decodeAudioChunkMessage>);
      ingestChunk({ message: chunk(), buffer: buffer as never, metadata: m, flowPaused: false });
    }

    expect(m.processedChunks).toBe(1);
  });

  it('advances once for a single-frame chunk', () => {
    const buffer = fakeBuffer();
    const m = meta();

    ingestChunk({ message: chunk(), buffer: buffer as never, metadata: m, flowPaused: false });

    expect(m.processedChunks).toBe(1);
  });

  it('reports progress as processed/total, clamped to 100', () => {
    const buffer = fakeBuffer();
    const m = meta({ totalChunks: 4, processedChunks: 0 });

    const first = ingestChunk({
      message: chunk(), buffer: buffer as never, metadata: m, flowPaused: false,
    });
    expect(first.clampedProgress).toBe(25);

    // More content chunks than announced must not push the bar past 100.
    m.processedChunks = 9;
    const overrun = ingestChunk({
      message: chunk(), buffer: buffer as never, metadata: m, flowPaused: false,
    });
    expect(overrun.clampedProgress).toBe(100);
  });

  it('surfaces the flow-control decision from the buffer fill level', () => {
    const full = fakeBuffer({ fillPct: 90 });
    expect(
      ingestChunk({ message: chunk(), buffer: full as never, metadata: meta(), flowPaused: false })
        .flowControl
    ).toBe('pause');

    const drained = fakeBuffer({ fillPct: 20 });
    expect(
      ingestChunk({ message: chunk(), buffer: drained as never, metadata: meta(), flowPaused: true })
        .flowControl
    ).toBe('resume');
  });

  it('returns the buffered sample count and decoder metadata', () => {
    const buffer = fakeBuffer({ available: 88200 });
    mockDecode.mockReturnValue({
      samples: new Float32Array(256),
      metadata: { chunkIndex: 7, frameIndex: 1, frameCount: 2, sampleCount: 256 },
    } as ReturnType<typeof decodeAudioChunkMessage>);

    const result = ingestChunk({
      message: chunk(), buffer: buffer as never, metadata: meta(), flowPaused: false,
    });

    expect(result.bufferedSamples).toBe(88200);
    expect(result).toMatchObject({ chunkIndex: 7, frameIndex: 1, frameCount: 2, sampleCount: 256 });
  });

  it('propagates a decoder failure so the caller can surface it', () => {
    mockDecode.mockImplementation(() => {
      throw new Error('Invalid sample_count in audio_chunk');
    });

    expect(() =>
      ingestChunk({ message: chunk(), buffer: fakeBuffer() as never, metadata: meta(), flowPaused: false })
    ).toThrow('Invalid sample_count');
  });
});
