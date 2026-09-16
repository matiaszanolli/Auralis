/**
 * PCM Decoding Utilities Tests
 *
 * Tests for audio_chunk message decoding (binary pcm_binary transport only,
 * #5423 -- the base64 `samples` fallback and its decoder were removed).
 */

import { describe, it, expect } from 'vitest';
import type { AudioChunkMessage } from '@/types/websocket';
import { decodeAudioChunkMessage } from '../pcmDecoding';

// The cases below deliberately build partial or malformed messages that the
// strict AudioChunkMessage type would reject at compile time.
const asChunk = (message: unknown) => message as AudioChunkMessage;

describe('PCM Decoding Utilities', () => {
  describe('decodeAudioChunkMessage', () => {
    it('should decode complete audio chunk message', () => {
      const testData = new Float32Array([0.1, 0.2, 0.3, 0.4]);

      const message = {
        type: 'audio_chunk',
        data: {
          chunk_index: 0,
          chunk_count: 5,
          frame_index: 0,
          frame_count: 1,
          pcm_binary: testData.buffer,
          sample_count: 4,
        },
      };

      const { samples, metadata } = decodeAudioChunkMessage(asChunk(message), 48000, 2);

      expect(samples.length).toBe(4);
      expect(metadata.sampleRate).toBe(48000);
      expect(metadata.channels).toBe(2);
      expect(metadata.chunkIndex).toBe(0);
    });

    it('should handle missing optional fields with defaults', () => {
      const testData = new Float32Array([0.1, 0.2]);

      const message = {
        type: 'audio_chunk',
        data: {
          pcm_binary: testData.buffer,
          sample_count: 2,
        },
      };

      const { metadata } = decodeAudioChunkMessage(asChunk(message), 48000, 2);

      expect(metadata.chunkIndex).toBe(0);
      expect(metadata.chunkCount).toBe(1);
    });

    it('should throw on invalid message format', () => {
      const invalidMessage = {
        type: 'audio_chunk',
        // Missing data field
      };

      expect(() => decodeAudioChunkMessage(asChunk(invalidMessage), 48000, 2)).toThrow();
    });

    it('should throw on missing pcm_binary field', () => {
      const invalidMessage = {
        type: 'audio_chunk',
        data: {
          sample_count: 10,
          // Missing pcm_binary field
        },
      };

      expect(() => decodeAudioChunkMessage(asChunk(invalidMessage), 48000, 2)).toThrow();
    });

    it('should throw on a stray base64 samples string instead of decoding it (#5423)', () => {
      // A malformed frame carrying the pre-#2764 legacy field but no
      // pcm_binary must fail loudly, not silently decode base64 garbage.
      const invalidMessage = {
        type: 'audio_chunk',
        data: {
          samples: 'AAAAAAAAAA==',
          sample_count: 2,
          // Missing pcm_binary field
        },
      };

      expect(() => decodeAudioChunkMessage(asChunk(invalidMessage), 48000, 2)).toThrow();
    });

    it('should throw on invalid sample count', () => {
      const testData = new Float32Array([0.1, 0.2]);

      const message = {
        type: 'audio_chunk',
        data: {
          pcm_binary: testData.buffer,
          sample_count: -1, // Invalid
        },
      };

      expect(() => decodeAudioChunkMessage(asChunk(message), 48000, 2)).toThrow();
    });

    it('should warn on sample count mismatch', () => {
      const testData = new Float32Array([0.1, 0.2]);

      const message = {
        type: 'audio_chunk',
        data: {
          pcm_binary: testData.buffer,
          sample_count: 999, // Mismatch: actually 2
        },
      };

      // Should not throw, but may warn
      const { samples } = decodeAudioChunkMessage(asChunk(message), 48000, 2);
      expect(samples.length).toBe(2); // Actual decoded length
    });
  });
});
