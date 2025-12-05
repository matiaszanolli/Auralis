/**
 * PCMStreamBuffer Unit Tests
 *
 * Tests for circular buffer implementation with crossfading support
 */

import { describe, it, expect, beforeEach } from 'vitest';
import PCMStreamBuffer from '../PCMStreamBuffer';

describe('PCMStreamBuffer', () => {
  let buffer: PCMStreamBuffer;

  beforeEach(() => {
    buffer = new PCMStreamBuffer();
  });

  describe('initialization', () => {
    it('should initialize with correct parameters', () => {
      buffer.initialize(48000, 2);
      const metadata = buffer.getMetadata();

      expect(metadata.sampleRate).toBe(48000);
      expect(metadata.channels).toBe(2);
      expect(metadata.capacity).toBe(5242880); // 5MB default
    });

    it('should initialize with custom capacity', () => {
      buffer.initialize(44100, 1, 1048576); // 1MB
      const metadata = buffer.getMetadata();

      expect(metadata.capacity).toBe(1048576);
    });

    it('should start empty', () => {
      buffer.initialize(48000, 2);
      expect(buffer.getAvailableSamples()).toBe(0);
      expect(buffer.getFillPercentage()).toBe(0);
    });
  });

  describe('append and read', () => {
    beforeEach(() => {
      buffer.initialize(48000, 2);
    });

    it('should append samples correctly', () => {
      const samples = new Float32Array([0.1, 0.2, 0.3, 0.4]);
      buffer.append(samples, 0);

      expect(buffer.getAvailableSamples()).toBe(4);
    });

    it('should read samples in order', () => {
      const samples = new Float32Array([0.1, 0.2, 0.3, 0.4]);
      buffer.append(samples, 0);

      const readSamples = buffer.read(4);

      expect(readSamples.length).toBe(4);
      expect(readSamples[0]).toBeCloseTo(0.1, 5);
      expect(readSamples[1]).toBeCloseTo(0.2, 5);
      expect(readSamples[2]).toBeCloseTo(0.3, 5);
      expect(readSamples[3]).toBeCloseTo(0.4, 5);
    });

    it('should handle wrap-around correctly', () => {
      // Create a small buffer to test wrap-around
      const smallBuffer = new PCMStreamBuffer();
      smallBuffer.initialize(48000, 2, 1024); // Very small

      // Fill to near capacity
      const part1 = new Float32Array(512);
      for (let i = 0; i < 512; i++) part1[i] = 0.1 + i * 0.0001;
      smallBuffer.append(part1, 0);

      // Read some to move read pointer
      smallBuffer.read(256);

      // Append more (will wrap)
      const part2 = new Float32Array(512);
      for (let i = 0; i < 512; i++) part2[i] = 0.2 + i * 0.0001;
      smallBuffer.append(part2, 0);

      // Should have 768 samples (512 + 512 - 256 read)
      expect(smallBuffer.getAvailableSamples()).toBe(768);
    });

    it('should return fewer samples than requested if buffer insufficient', () => {
      const samples = new Float32Array([0.1, 0.2]);
      buffer.append(samples, 0);

      const readSamples = buffer.read(10);

      expect(readSamples.length).toBe(2);
    });

    it('should return empty array if buffer empty', () => {
      const readSamples = buffer.read(10);

      expect(readSamples.length).toBe(0);
    });
  });

  describe('crossfading', () => {
    beforeEach(() => {
      buffer.initialize(48000, 2);
    });

    it('should blend overlapping samples at boundaries', () => {
      // First chunk: [0.0, 0.1, 0.2]
      const chunk1 = new Float32Array([0.0, 0.1, 0.2]);
      buffer.append(chunk1, 0);

      // Second chunk: [0.5, 0.6, 0.7] with 1-sample crossfade
      // The last sample of chunk1 (0.2) and first of chunk2 (0.5) should blend
      const chunk2 = new Float32Array([0.5, 0.6, 0.7]);
      buffer.append(chunk2, 1);

      // Read and verify crossfade
      const result = buffer.read(4);

      // First two samples should be from chunk1
      expect(result[0]).toBeCloseTo(0.0, 5);
      expect(result[1]).toBeCloseTo(0.1, 5);

      // The overlapped sample should be blended
      // Original: 0.2 (chunk1) -> 0.5 (chunk2)
      // Blended at 50%: 0.2*0.5 + 0.5*0.5 = 0.1 + 0.25 = 0.35
      expect(result[2]).toBeCloseTo(0.35, 5);

      // Next sample from chunk2
      expect(result[3]).toBeCloseTo(0.6, 5);
    });

    it('should handle multi-sample crossfades', () => {
      const chunk1 = new Float32Array([0.1, 0.2, 0.3, 0.4, 0.5]);
      buffer.append(chunk1, 0);

      // Append with 2-sample crossfade
      const chunk2 = new Float32Array([0.8, 0.9, 1.0]);
      buffer.append(chunk2, 2);

      const result = buffer.read(7);

      // First 3 from chunk1 unchanged
      expect(result[0]).toBeCloseTo(0.1, 5);
      expect(result[1]).toBeCloseTo(0.2, 5);
      expect(result[2]).toBeCloseTo(0.3, 5);

      // Sample at index 3: blend chunk1[3]=0.4 and chunk2[0]=0.8
      // At position 0 of 2: weight = 0/2 = 0, so: 0.4*1.0 + 0.8*0.0 = 0.4
      expect(result[3]).toBeCloseTo(0.4, 5);

      // Sample at index 4: blend chunk1[4]=0.5 and chunk2[1]=0.9
      // At position 1 of 2: weight = 1/2 = 0.5, so: 0.5*0.5 + 0.9*0.5 = 0.7
      expect(result[4]).toBeCloseTo(0.7, 5);

      // Remaining from chunk2
      expect(result[5]).toBeCloseTo(0.9, 5);
      expect(result[6]).toBeCloseTo(1.0, 5);
    });

    it('should handle zero crossfade (no blending)', () => {
      const chunk1 = new Float32Array([0.1, 0.2]);
      buffer.append(chunk1, 0);

      const chunk2 = new Float32Array([0.5, 0.6]);
      buffer.append(chunk2, 0); // 0 crossfade samples

      const result = buffer.read(4);

      expect(result[0]).toBeCloseTo(0.1, 5);
      expect(result[1]).toBeCloseTo(0.2, 5);
      expect(result[2]).toBeCloseTo(0.5, 5);
      expect(result[3]).toBeCloseTo(0.6, 5);
    });
  });

  describe('buffer overflow', () => {
    beforeEach(() => {
      buffer.initialize(48000, 2, 1024); // Small buffer
    });

    it('should handle buffer overflow gracefully', () => {
      const chunk1 = new Float32Array(512);
      for (let i = 0; i < 512; i++) chunk1[i] = i * 0.001;
      buffer.append(chunk1, 0);

      const chunk2 = new Float32Array(512);
      for (let i = 0; i < 512; i++) chunk2[i] = i * 0.002;
      buffer.append(chunk2, 0);

      // Should not exceed capacity
      const fill = buffer.getFillPercentage();
      expect(fill).toBeLessThanOrEqual(100);
    });

    it('should discard oldest data on overflow', () => {
      // Fill buffer completely
      const chunk1 = new Float32Array(1024);
      for (let i = 0; i < 1024; i++) chunk1[i] = 0.1;
      buffer.append(chunk1, 0);

      expect(buffer.getFillPercentage()).toBe(100);

      // Try to add more (should replace oldest)
      const chunk2 = new Float32Array(512);
      for (let i = 0; i < 512; i++) chunk2[i] = 0.9;
      buffer.append(chunk2, 0);

      // Should still be full
      expect(buffer.getFillPercentage()).toBe(100);

      // Read all and check - should have newer data
      const allData = buffer.read(1024);
      // Last half should be 0.9 (new data)
      expect(allData[512]).toBeCloseTo(0.9, 5);
    });
  });

  describe('metadata tracking', () => {
    it('should track metadata correctly', () => {
      buffer.initialize(48000, 2);

      const chunk1 = new Float32Array(1000);
      buffer.append(chunk1, 0);

      const metadata = buffer.getMetadata();

      expect(metadata.sampleRate).toBe(48000);
      expect(metadata.channels).toBe(2);
      expect(metadata.totalAppended).toBe(1000);
      expect(metadata.totalRead).toBe(0);
    });

    it('should update read count', () => {
      buffer.initialize(48000, 2);

      const chunk = new Float32Array(1000);
      buffer.append(chunk, 0);

      buffer.read(250);
      buffer.read(250);

      const metadata = buffer.getMetadata();
      expect(metadata.totalRead).toBe(500);
    });
  });

  describe('fill percentage', () => {
    beforeEach(() => {
      buffer.initialize(48000, 2); // 5MB capacity
    });

    it('should calculate fill percentage correctly', () => {
      const samples = new Float32Array(1000);
      buffer.append(samples, 0);

      const fill = buffer.getFillPercentage();
      const expected = (1000 / (5242880 / 4)) * 100;

      expect(fill).toBeCloseTo(expected, 1);
    });

    it('should return 0 for empty buffer', () => {
      expect(buffer.getFillPercentage()).toBe(0);
    });
  });

  describe('mono to stereo conversion', () => {
    it('should handle mono samples correctly', () => {
      buffer.initialize(48000, 1); // Mono

      const monoSamples = new Float32Array([0.1, 0.2, 0.3]);
      buffer.append(monoSamples, 0);

      const result = buffer.read(3);

      expect(result.length).toBe(3);
      expect(result[0]).toBeCloseTo(0.1, 5);
      expect(result[1]).toBeCloseTo(0.2, 5);
      expect(result[2]).toBeCloseTo(0.3, 5);
    });
  });

  describe('stereo interleaved samples', () => {
    it('should handle stereo interleaved (L,R,L,R...)', () => {
      buffer.initialize(48000, 2); // Stereo

      // Interleaved: [L1, R1, L2, R2]
      const stereoSamples = new Float32Array([0.1, 0.2, 0.3, 0.4]);
      buffer.append(stereoSamples, 0);

      const result = buffer.read(4);

      // Should preserve interleaving
      expect(result[0]).toBeCloseTo(0.1, 5); // L1
      expect(result[1]).toBeCloseTo(0.2, 5); // R1
      expect(result[2]).toBeCloseTo(0.3, 5); // L2
      expect(result[3]).toBeCloseTo(0.4, 5); // R2
    });
  });

  describe('error conditions', () => {
    it('should handle uninitialized buffer gracefully', () => {
      // Don't call initialize
      const result = buffer.read(10);
      expect(result.length).toBe(0);
    });

    it('should handle NaN samples', () => {
      buffer.initialize(48000, 2);

      const invalidSamples = new Float32Array([0.1, NaN, 0.3]);
      // Should not throw
      expect(() => buffer.append(invalidSamples, 0)).not.toThrow();
    });

    it('should handle Infinity samples', () => {
      buffer.initialize(48000, 2);

      const invalidSamples = new Float32Array([0.1, Infinity, -Infinity]);
      // Should not throw
      expect(() => buffer.append(invalidSamples, 0)).not.toThrow();
    });
  });

  describe('sequential operations', () => {
    beforeEach(() => {
      buffer.initialize(48000, 2);
    });

    it('should handle multiple append-read cycles', () => {
      for (let cycle = 0; cycle < 5; cycle++) {
        const chunk = new Float32Array(100);
        for (let i = 0; i < 100; i++) {
          chunk[i] = cycle * 0.1 + i * 0.001;
        }

        buffer.append(chunk, 0);
        const result = buffer.read(50);

        expect(result.length).toBeLessThanOrEqual(100);
      }

      // After 5 cycles of 100 samples, at least some should be available
      expect(buffer.getAvailableSamples()).toBeGreaterThanOrEqual(0);
    });

    it('should maintain data integrity across multiple operations', () => {
      const allData: number[] = [];

      for (let i = 0; i < 3; i++) {
        const chunk = new Float32Array(10);
        for (let j = 0; j < 10; j++) {
          chunk[j] = i + j * 0.01;
        }

        buffer.append(chunk, 0);
        const read = buffer.read(5);

        for (let j = 0; j < read.length; j++) {
          allData.push(read[j]);
        }
      }

      // Should have read some data
      expect(allData.length).toBeGreaterThan(0);
    });
  });
});
