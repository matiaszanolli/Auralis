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
      expect(metadata.capacity).toBe(100 * 1024 * 1024); // 100MB default
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
      buffer.append(samples);

      expect(buffer.getAvailableSamples()).toBe(4);
    });

    it('should read samples in order', () => {
      const samples = new Float32Array([0.1, 0.2, 0.3, 0.4]);
      buffer.append(samples);

      const readSamples = buffer.read(4);

      expect(readSamples.length).toBe(4);
      expect(readSamples[0]).toBeCloseTo(0.1, 5);
      expect(readSamples[1]).toBeCloseTo(0.2, 5);
      expect(readSamples[2]).toBeCloseTo(0.3, 5);
      expect(readSamples[3]).toBeCloseTo(0.4, 5);
    });

    it('should handle wrap-around correctly', () => {
      // Create a buffer large enough to test wrap-around (3072 bytes = 768 samples + 1)
      const smallBuffer = new PCMStreamBuffer();
      smallBuffer.initialize(48000, 2, 3072);

      // Fill to near capacity
      const part1 = new Float32Array(512);
      for (let i = 0; i < 512; i++) part1[i] = 0.1 + i * 0.0001;
      smallBuffer.append(part1);

      // Read some to move read pointer
      smallBuffer.read(256);

      // Append more (will wrap around the circular buffer)
      const part2 = new Float32Array(512);
      for (let i = 0; i < 512; i++) part2[i] = 0.2 + i * 0.0001;
      smallBuffer.append(part2);

      // Should have 768 samples (512 + 512 - 256 read)
      expect(smallBuffer.getAvailableSamples()).toBe(768);
    });

    it('should return fewer samples than requested if buffer insufficient', () => {
      const samples = new Float32Array([0.1, 0.2]);
      buffer.append(samples);

      const readSamples = buffer.read(10);

      expect(readSamples.length).toBe(2);
    });

    it('should return empty array if buffer empty', () => {
      const readSamples = buffer.read(10);

      expect(readSamples.length).toBe(0);
    });
  });

  describe('chunk concatenation', () => {
    // #4642: the buffer no longer crossfades. Chunks arrive already trimmed to
    // non-overlapping segments by the server, so appended chunks are simply
    // concatenated — the linear-fade path (and its crossfadeSamples argument)
    // was permanently unreachable and has been removed.
    beforeEach(() => {
      buffer.initialize(48000, 2);
    });

    it('should concatenate consecutive chunks without blending', () => {
      buffer.append(new Float32Array([0.1, 0.2]));
      buffer.append(new Float32Array([0.5, 0.6]));

      const result = buffer.read(4);

      expect(result[0]).toBeCloseTo(0.1, 5);
      expect(result[1]).toBeCloseTo(0.2, 5);
      expect(result[2]).toBeCloseTo(0.5, 5);
      expect(result[3]).toBeCloseTo(0.6, 5);
    });

    it('should leave every sample of every chunk bit-identical', () => {
      const chunks = [
        new Float32Array([0.1, 0.2, 0.3, 0.4, 0.5]),
        new Float32Array([0.8, 0.9, 1.0]),
        new Float32Array([-0.5, -0.25]),
      ];
      for (const chunk of chunks) buffer.append(chunk);

      const expected = Float32Array.from(chunks.flatMap((c) => [...c]));
      const result = buffer.read(expected.length);

      expect(Array.from(result)).toEqual(Array.from(expected));
    });

    it('should not modify the caller\'s input array', () => {
      const chunk = new Float32Array([0.1, 0.2, 0.3]);
      const copy = new Float32Array(chunk);

      buffer.append(chunk);
      buffer.append(new Float32Array([0.4, 0.5, 0.6]));

      expect(Array.from(chunk)).toEqual(Array.from(copy));
    });
  });

  describe('buffer overflow', () => {
    beforeEach(() => {
      buffer.initialize(48000, 2, 1024); // Small buffer
    });

    it('should handle buffer overflow gracefully', () => {
      const chunk1 = new Float32Array(512);
      for (let i = 0; i < 512; i++) chunk1[i] = i * 0.001;
      buffer.append(chunk1);

      const chunk2 = new Float32Array(512);
      for (let i = 0; i < 512; i++) chunk2[i] = i * 0.002;
      buffer.append(chunk2);

      // Should not exceed capacity
      const fill = buffer.getFillPercentage();
      expect(fill).toBeLessThanOrEqual(100);
    });

    it('should drop new data on overflow to preserve playback position', () => {
      // Fill buffer to capacity (256 samples = 1024 bytes / 4 bytes per sample)
      const chunk1 = new Float32Array(256);
      for (let i = 0; i < 256; i++) chunk1[i] = 0.1;
      buffer.append(chunk1);

      expect(buffer.getFillPercentage()).toBe(100);

      // Try to add more - should drop new data to preserve playback position
      const chunk2 = new Float32Array(128);
      for (let i = 0; i < 128; i++) chunk2[i] = 0.9;
      buffer.append(chunk2);

      // Should still be full with original data (new data was dropped)
      expect(buffer.getFillPercentage()).toBe(100);

      // Read all and verify original data is preserved
      const allData = buffer.read(256);
      // All data should be 0.1 (original data preserved, new data dropped)
      expect(allData[0]).toBeCloseTo(0.1, 5);
      expect(allData[128]).toBeCloseTo(0.1, 5);
      expect(allData[255]).toBeCloseTo(0.1, 5);
    });
  });

  describe('metadata tracking', () => {
    it('should track metadata correctly', () => {
      buffer.initialize(48000, 2);

      const chunk1 = new Float32Array(1000);
      buffer.append(chunk1);

      const metadata = buffer.getMetadata();

      expect(metadata.sampleRate).toBe(48000);
      expect(metadata.channels).toBe(2);
      expect(metadata.totalAppended).toBe(1000);
      expect(metadata.totalRead).toBe(0);
    });

    it('should update read count', () => {
      buffer.initialize(48000, 2);

      const chunk = new Float32Array(1000);
      buffer.append(chunk);

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
      buffer.append(samples);

      const fill = buffer.getFillPercentage();
      const metadata = buffer.getMetadata();
      const expected = (1000 / (metadata.capacity / 4)) * 100;

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
      buffer.append(monoSamples);

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
      buffer.append(stereoSamples);

      const result = buffer.read(4);

      // Should preserve interleaving
      expect(result[0]).toBeCloseTo(0.1, 5); // L1
      expect(result[1]).toBeCloseTo(0.2, 5); // R1
      expect(result[2]).toBeCloseTo(0.3, 5); // L2
      expect(result[3]).toBeCloseTo(0.4, 5); // R2
    });
  });

  describe('error conditions', () => {
    it('should throw error when reading from uninitialized buffer', () => {
      // Don't call initialize
      expect(() => buffer.read(10)).toThrow('PCMStreamBuffer not initialized');
    });

    it('should handle NaN samples', () => {
      buffer.initialize(48000, 2);

      const invalidSamples = new Float32Array([0.1, NaN, 0.3]);
      // Should not throw
      expect(() => buffer.append(invalidSamples)).not.toThrow();
    });

    it('should handle Infinity samples', () => {
      buffer.initialize(48000, 2);

      const invalidSamples = new Float32Array([0.1, Infinity, -Infinity]);
      // Should not throw
      expect(() => buffer.append(invalidSamples)).not.toThrow();
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

        buffer.append(chunk);
        const result = buffer.read(50);

        expect(result.length).toBeLessThanOrEqual(100);
      }

      // Each cycle retains 50 of the 100 appended samples.
      expect(buffer.getAvailableSamples()).toBe(250);
    });

    it('should maintain data integrity across multiple operations', () => {
      const allData: number[] = [];

      for (let i = 0; i < 3; i++) {
        const chunk = new Float32Array(10);
        for (let j = 0; j < 10; j++) {
          chunk[j] = i + j * 0.01;
        }

        buffer.append(chunk);
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
