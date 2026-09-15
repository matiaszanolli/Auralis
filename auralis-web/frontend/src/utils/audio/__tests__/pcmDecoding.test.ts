/**
 * PCM Decoding Utilities Tests
 *
 * Tests for base64 decoding and audio_chunk message decoding
 */

import { describe, it, expect } from 'vitest';
import type { AudioChunkMessage } from '@/types/websocket';
import {
  decodePCMBase64,
  decodeAudioChunkMessage,
} from '../pcmDecoding';

// The cases below deliberately build partial or malformed messages that the
// strict AudioChunkMessage type would reject at compile time.
const asChunk = (message: unknown) => message as AudioChunkMessage;

describe('PCM Decoding Utilities', () => {
  describe('decodePCMBase64', () => {
    it('should decode base64-encoded PCM data correctly', () => {
      // Create test data: [1.0, 0.5, -0.5, 0.0]
      const testData = new Float32Array([1.0, 0.5, -0.5, 0.0]);
      const bytes = new Uint8Array(testData.buffer);
      const base64 = btoa(String.fromCharCode(...bytes));

      const decoded = decodePCMBase64(base64);

      expect(decoded.length).toBe(4);
      expect(decoded[0]).toBeCloseTo(1.0, 5);
      expect(decoded[1]).toBeCloseTo(0.5, 5);
      expect(decoded[2]).toBeCloseTo(-0.5, 5);
      expect(decoded[3]).toBeCloseTo(0.0, 5);
    });

    it('should handle empty base64 string', () => {
      const decoded = decodePCMBase64('');
      expect(decoded.length).toBe(0);
    });

    it('should throw on invalid base64', () => {
      expect(() => decodePCMBase64('invalid!!!base64')).toThrow();
    });

    it('should throw on non-divisible sample count', () => {
      // Create 3 bytes (not divisible by 4)
      const bytes = new Uint8Array([1, 2, 3]);
      const base64 = btoa(String.fromCharCode(...bytes));

      expect(() => decodePCMBase64(base64)).toThrow();
    });
  });

  describe('decodeAudioChunkMessage', () => {
    it('should decode complete audio chunk message', () => {
      // Create test PCM data
      const testData = new Float32Array([0.1, 0.2, 0.3, 0.4]);
      const bytes = new Uint8Array(testData.buffer);
      const base64 = btoa(String.fromCharCode(...bytes));

      const message = {
        type: 'audio_chunk',
        data: {
          chunk_index: 0,
          chunk_count: 5,
          frame_index: 0,
          frame_count: 1,
          samples: base64,
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
      const bytes = new Uint8Array(testData.buffer);
      const base64 = btoa(String.fromCharCode(...bytes));

      const message = {
        type: 'audio_chunk',
        data: {
          samples: base64,
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

    it('should throw on missing samples field', () => {
      const invalidMessage = {
        type: 'audio_chunk',
        data: {
          sample_count: 10,
          // Missing samples field
        },
      };

      expect(() => decodeAudioChunkMessage(asChunk(invalidMessage), 48000, 2)).toThrow();
    });

    it('should throw on invalid sample count', () => {
      const testData = new Float32Array([0.1, 0.2]);
      const bytes = new Uint8Array(testData.buffer);
      const base64 = btoa(String.fromCharCode(...bytes));

      const message = {
        type: 'audio_chunk',
        data: {
          samples: base64,
          sample_count: -1, // Invalid
        },
      };

      expect(() => decodeAudioChunkMessage(asChunk(message), 48000, 2)).toThrow();
    });

    it('should warn on sample count mismatch', () => {
      const testData = new Float32Array([0.1, 0.2]);
      const bytes = new Uint8Array(testData.buffer);
      const base64 = btoa(String.fromCharCode(...bytes));

      const message = {
        type: 'audio_chunk',
        data: {
          samples: base64,
          sample_count: 999, // Mismatch: actually 2
        },
      };

      // Should not throw, but may warn
      const { samples } = decodeAudioChunkMessage(asChunk(message), 48000, 2);
      expect(samples.length).toBe(2); // Actual decoded length
    });
  });
});
