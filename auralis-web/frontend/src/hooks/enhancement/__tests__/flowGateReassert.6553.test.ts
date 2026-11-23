/**
 * A paused client's full ring is never overrun silently (#6553).
 *
 * The backend's bounded flow gate kept sending one chunk per 30 s to a client
 * whose user pause meant it never drained, never sent buffer_ready and never
 * repeated buffer_full; the PCM ring then dropped whole frames with only a
 * console.warn while ingest counted them as played. Now a chunk that lands
 * above the pause mark re-asserts buffer_full (once per content chunk), and a
 * frame the ring rejects is reported, not counted.
 */

import { describe, it, expect, vi } from 'vitest';
import { PCMStreamBuffer } from '@/services/audio/PCMStreamBuffer';
import { ingestChunk, nextFlowControlSignal, FLOW_PAUSE_FILL_PCT } from '../audioChunkIngest';
import type { StreamingMetadata } from '../useAudioStreamingCore';
import type { AudioChunkMessage } from '@/contexts/WebSocketContext';

vi.mock('@/utils/audio/pcmDecoding', () => ({ decodeAudioChunkMessage: vi.fn() }));
import { decodeAudioChunkMessage } from '@/utils/audio/pcmDecoding';

const message = { type: 'audio_chunk', data: { chunk_index: 3 } } as unknown as AudioChunkMessage;

function smallRing(capacitySamples: number) {
  const buffer = new PCMStreamBuffer(capacitySamples * 4);
  buffer.initialize(44100, 2);
  return buffer;
}

function decodes(samples: number, frameIndex = 0, frameCount = 1) {
  vi.mocked(decodeAudioChunkMessage).mockReturnValue({
    samples: new Float32Array(samples),
    metadata: { chunkIndex: 3, frameIndex, frameCount, sampleCount: samples },
  } as unknown as ReturnType<typeof decodeAudioChunkMessage>);
}

describe('PCMStreamBuffer.append (#6553)', () => {
  it('reports a frame it cannot hold and leaves the ring unchanged', () => {
    const ring = smallRing(1000);
    expect(ring.append(new Float32Array(900))).toBe(true);

    expect(ring.append(new Float32Array(200))).toBe(false);
    expect(ring.getAvailableSamples()).toBe(900);
  });
});

describe('ingestChunk with a full ring (#6553)', () => {
  it('does not count a dropped frame as ingested and asks the backend to hold', () => {
    const ring = smallRing(1000);
    ring.append(new Float32Array(900));
    const metadata = { sampleRate: 44100, channels: 2, totalChunks: 10, processedChunks: 4 } as StreamingMetadata;
    decodes(200);

    const result = ingestChunk({ message, buffer: ring, metadata, flowPaused: true });

    expect(result.rejected).toBe(true);
    expect(result.flowControl).toBe('pause');
    expect(metadata.processedChunks).toBe(4);
  });
});

describe('nextFlowControlSignal re-asserts a held pause (#6553)', () => {
  const above = FLOW_PAUSE_FILL_PCT + 5;

  it('re-sends pause for a completed chunk that still lands above the mark', () => {
    expect(nextFlowControlSignal(above, true, true)).toBe('pause');
  });

  it('stays quiet on intermediate sub-frames so buffer_full is not spammed', () => {
    expect(nextFlowControlSignal(above, true, false)).toBeNull();
  });

  it('still sends the first pause and the resume as before', () => {
    expect(nextFlowControlSignal(above, false, false)).toBe('pause');
    expect(nextFlowControlSignal(10, true, true)).toBe('resume');
  });
});
