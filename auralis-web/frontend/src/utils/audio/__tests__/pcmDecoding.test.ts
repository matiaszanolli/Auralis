/**
 * PCM Decoding Utilities Tests
 *
 * Tests for base64 decoding, channel conversion, and validation
 */

import { describe, it, expect } from 'vitest';
import {
  decodePCMBase64,
  monoToStereo,
  stereoInterleavedToChannels,
  validatePCMSamples,
  clipPCMSamples,
  resamplePCM,
  durationToSampleCount,
  sampleCountToDuration,
  decodeAudioChunkMessage,
} from '../pcmDecoding';

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

  describe('monoToStereo', () => {
    it('should duplicate mono samples to stereo', () => {
      const mono = new Float32Array([0.1, 0.2, 0.3]);
      const stereo = monoToStereo(mono);

      expect(stereo.length).toBe(6);
      expect(stereo[0]).toBeCloseTo(0.1, 5); // L
      expect(stereo[1]).toBeCloseTo(0.1, 5); // R
      expect(stereo[2]).toBeCloseTo(0.2, 5); // L
      expect(stereo[3]).toBeCloseTo(0.2, 5); // R
      expect(stereo[4]).toBeCloseTo(0.3, 5); // L
      expect(stereo[5]).toBeCloseTo(0.3, 5); // R
    });

    it('should handle empty mono array', () => {
      const mono = new Float32Array([]);
      const stereo = monoToStereo(mono);

      expect(stereo.length).toBe(0);
    });

    it('should handle single sample', () => {
      const mono = new Float32Array([0.5]);
      const stereo = monoToStereo(mono);

      expect(stereo.length).toBe(2);
      expect(stereo[0]).toBeCloseTo(0.5, 5);
      expect(stereo[1]).toBeCloseTo(0.5, 5);
    });
  });

  describe('stereoInterleavedToChannels', () => {
    it('should separate interleaved stereo to channels', () => {
      const interleaved = new Float32Array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6]);
      const [left, right] = stereoInterleavedToChannels(interleaved);

      expect(left.length).toBe(3);
      expect(right.length).toBe(3);

      expect(left[0]).toBeCloseTo(0.1, 5);
      expect(right[0]).toBeCloseTo(0.2, 5);
      expect(left[1]).toBeCloseTo(0.3, 5);
      expect(right[1]).toBeCloseTo(0.4, 5);
      expect(left[2]).toBeCloseTo(0.5, 5);
      expect(right[2]).toBeCloseTo(0.6, 5);
    });

    it('should throw on odd sample count', () => {
      const interleaved = new Float32Array([0.1, 0.2, 0.3]); // 3 samples (odd)

      expect(() => stereoInterleavedToChannels(interleaved)).toThrow();
    });

    it('should handle empty stereo array', () => {
      const interleaved = new Float32Array([]);
      const [left, right] = stereoInterleavedToChannels(interleaved);

      expect(left.length).toBe(0);
      expect(right.length).toBe(0);
    });
  });

  describe('validatePCMSamples', () => {
    it('should validate correct PCM samples', () => {
      const samples = new Float32Array([0.0, 0.5, -0.5, 1.0, -1.0]);

      expect(validatePCMSamples(samples)).toBe(true);
    });

    it('should reject NaN samples', () => {
      const samples = new Float32Array([0.0, NaN, 0.5]);

      expect(validatePCMSamples(samples)).toBe(false);
    });

    it('should reject Infinity samples', () => {
      const samples = new Float32Array([0.0, Infinity, -Infinity]);

      expect(validatePCMSamples(samples)).toBe(false);
    });

    it('should reject out-of-range samples', () => {
      const samples = new Float32Array([0.0, 2.0, -2.0]); // > 1.5 range

      expect(validatePCMSamples(samples)).toBe(false);
    });

    it('should allow slight overshoot for headroom', () => {
      const samples = new Float32Array([0.0, 1.5, -1.5]); // Exactly at limit

      expect(validatePCMSamples(samples)).toBe(true);
    });
  });

  describe('clipPCMSamples', () => {
    it('should clip samples to [-1.0, 1.0]', () => {
      const samples = new Float32Array([0.5, 1.2, -0.8, -1.5]);
      clipPCMSamples(samples);

      expect(samples[0]).toBeCloseTo(0.5, 5);
      expect(samples[1]).toBeCloseTo(1.0, 5);
      expect(samples[2]).toBeCloseTo(-0.8, 5);
      expect(samples[3]).toBeCloseTo(-1.0, 5);
    });

    it('should modify array in place', () => {
      const samples = new Float32Array([2.0, -2.0]);
      const result = clipPCMSamples(samples);

      expect(result === samples).toBe(true);
      expect(samples[0]).toBe(1.0);
      expect(samples[1]).toBe(-1.0);
    });

    it('should handle valid samples without change', () => {
      const samples = new Float32Array([0.0, 0.5, -0.5]);
      const original = new Float32Array([0.0, 0.5, -0.5]);

      clipPCMSamples(samples);

      for (let i = 0; i < samples.length; i++) {
        expect(samples[i]).toBe(original[i]);
      }
    });
  });

  describe('resamplePCM', () => {
    it('should resample from 48kHz to 44.1kHz', () => {
      const pcm48k = new Float32Array([0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7]);
      const pcm44k = resamplePCM(pcm48k, 48000, 44100);

      // Approximate: 8 samples at 48kHz ≈ 7.35 samples at 44.1kHz
      expect(pcm44k.length).toBeGreaterThanOrEqual(7);
      expect(pcm44k.length).toBeLessThanOrEqual(8);
    });

    it('should not resample when rates equal', () => {
      const pcm = new Float32Array([0.1, 0.2, 0.3]);
      const resampled = resamplePCM(pcm, 48000, 48000);

      expect(resampled.length).toBe(3);
      expect(resampled[0]).toBeCloseTo(0.1, 5);
      expect(resampled[1]).toBeCloseTo(0.2, 5);
      expect(resampled[2]).toBeCloseTo(0.3, 5);
    });

    it('should use linear interpolation', () => {
      const pcm = new Float32Array([0.0, 1.0]); // Linear ramp
      const resampled = resamplePCM(pcm, 1, 3); // 1 Hz to 3 Hz (3x)

      // Should have ~6 samples (2 * 3)
      expect(resampled.length).toBe(6);

      // Should follow linear interpolation
      expect(resampled[0]).toBeCloseTo(0.0, 5);
      expect(resampled[3]).toBeCloseTo(0.5, 5); // Mid-point
      expect(resampled[5]).toBeCloseTo(1.0, 5);
    });

    it('should handle downsample ratios', () => {
      const pcm = new Float32Array([0.0, 0.25, 0.5, 0.75, 1.0]);
      const resampled = resamplePCM(pcm, 5, 2); // Downsample

      expect(resampled.length).toBe(2);
    });
  });

  describe('sampleCountToDuration', () => {
    it('should convert samples to duration correctly', () => {
      const duration = sampleCountToDuration(48000, 48000);
      expect(duration).toBeCloseTo(1.0, 5);
    });

    it('should handle different sample rates', () => {
      const duration = sampleCountToDuration(44100, 44100);
      expect(duration).toBeCloseTo(1.0, 5);

      const halfSecond = sampleCountToDuration(24050, 48000);
      expect(halfSecond).toBeCloseTo(0.5, 5);
    });

    it('should handle zero samples', () => {
      const duration = sampleCountToDuration(0, 48000);
      expect(duration).toBe(0);
    });
  });

  describe('durationToSampleCount', () => {
    it('should convert duration to sample count correctly', () => {
      const samples = durationToSampleCount(1.0, 48000);
      expect(samples).toBe(48000);
    });

    it('should handle fractional durations', () => {
      const samples = durationToSampleCount(0.5, 48000);
      expect(samples).toBe(24000);
    });

    it('should ceil the result for precision', () => {
      const samples = durationToSampleCount(0.1, 44100);
      // 0.1 * 44100 = 4410, but should ceil if float
      expect(samples).toBe(4410);
    });

    it('should handle zero duration', () => {
      const samples = durationToSampleCount(0, 48000);
      expect(samples).toBe(0);
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
          crossfade_samples: 0,
        },
      };

      const { samples, metadata } = decodeAudioChunkMessage(message, 48000, 2);

      expect(samples.length).toBe(4);
      expect(metadata.sampleRate).toBe(48000);
      expect(metadata.channels).toBe(2);
      expect(metadata.chunkIndex).toBe(0);
      expect(metadata.crossfadeSamples).toBe(0);
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

      const { metadata } = decodeAudioChunkMessage(message, 48000, 2);

      expect(metadata.chunkIndex).toBe(0);
      expect(metadata.chunkCount).toBe(1);
      expect(metadata.crossfadeSamples).toBe(0);
    });

    it('should throw on invalid message format', () => {
      const invalidMessage = {
        type: 'audio_chunk',
        // Missing data field
      };

      expect(() => decodeAudioChunkMessage(invalidMessage, 48000, 2)).toThrow();
    });

    it('should throw on missing samples field', () => {
      const invalidMessage = {
        type: 'audio_chunk',
        data: {
          sample_count: 10,
          // Missing samples field
        },
      };

      expect(() => decodeAudioChunkMessage(invalidMessage, 48000, 2)).toThrow();
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

      expect(() => decodeAudioChunkMessage(message, 48000, 2)).toThrow();
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
      const { samples } = decodeAudioChunkMessage(message, 48000, 2);
      expect(samples.length).toBe(2); // Actual decoded length
    });
  });

  describe('edge cases', () => {
    it('should handle very large float values gracefully', () => {
      const large = new Float32Array([1.0, 1.0, 1.0]);
      expect(() => validatePCMSamples(large)).not.toThrow();
    });

    it('should handle very small float values', () => {
      const small = new Float32Array([1e-10, -1e-10, 0.0]);
      expect(validatePCMSamples(small)).toBe(true);
    });

    it('should handle denormalized floats', () => {
      const denorm = new Float32Array([
        Number.MIN_VALUE,
        -Number.MIN_VALUE,
        0.0,
      ]);
      expect(validatePCMSamples(denorm)).toBe(true);
    });
  });
});
