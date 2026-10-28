/**
 * A seek stream's progress counts from its start_chunk (#5931)
 *
 * audio_stream_start carries the whole track's total_chunks plus the start_chunk the stream
 * begins at. The numerator used to restart at 0, so after a seek to 80% the buffered bar
 * grew 0→20% instead of ending at 100%.
 */

import { describe, it, expect, vi } from 'vitest';
import { startChunkOffset } from '../useEnhancedStreamStart';
import { ingestChunk } from '../audioChunkIngest';

vi.mock('@/utils/audio/pcmDecoding', () => ({
  decodeAudioChunkMessage: () => ({
    samples: new Float32Array(0),
    metadata: { chunkIndex: 0, frameIndex: 0, frameCount: 1, sampleCount: 0 },
  }),
}));

describe('startChunkOffset', () => {
  it('passes a positive chunk index through', () => {
    expect(startChunkOffset(8)).toBe(8);
  });

  it.each([undefined, 0, -3, Number.NaN, Number.POSITIVE_INFINITY])('is 0 for %s', (value) => {
    expect(startChunkOffset(value)).toBe(0);
  });
});

describe('progress of a stream that starts mid-track', () => {
  const buffer = { append: vi.fn(), getFillPercentage: () => 0, getAvailableSamples: () => 0 };

  it('reaches 100% on the final chunk instead of stopping at remaining/total', () => {
    const total = 10;
    const metadata = { sampleRate: 44100, channels: 2, totalChunks: total, processedChunks: startChunkOffset(8) };
    const message = { type: 'audio_chunk', data: { samples: '' } };

    const first = ingestChunk({ message: message as never, buffer: buffer as never, metadata, flowPaused: false });
    const second = ingestChunk({ message: message as never, buffer: buffer as never, metadata, flowPaused: false });

    expect(first.clampedProgress).toBe(90);
    expect(second.clampedProgress).toBe(100);
  });
});
