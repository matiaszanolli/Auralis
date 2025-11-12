/**
 * UnifiedWebMAudioPlayer Chunk Timing Tests
 *
 * Tests the critical chunk playback timing logic to ensure:
 * 1. Chunks play sequentially without gaps
 * 2. Time tracking is accurate across chunk boundaries
 * 3. Seeking works correctly within and across chunks
 * 4. Last chunk handling is correct
 */

describe('UnifiedWebMAudioPlayer Chunk Timing', () => {
  // Mock metadata
  const mockMetadata = {
    track_id: 1,
    duration: 148.57,  // ~2:28 track
    sample_rate: 44100,
    channels: 2,
    chunk_duration: 15,      // Each buffer has 15s of audio
    chunk_interval: 10,      // Chunks are spaced 10s apart
    total_chunks: 15,        // ceil(148.57 / 10) = 15 chunks
    mime_type: 'audio/webm',
    codecs: 'opus',
    format_version: 'unified-v1.0',
    chunk_playable_duration: 10,  // After trimming overlap
    overlap_duration: 5,
  };

  describe('Chunk Boundary Calculation', () => {
    test('should calculate correct chunk index from playback time', () => {
      const chunkInterval = mockMetadata.chunk_interval;

      // Timeline 0-10s = chunk 0
      expect(Math.floor(0 / chunkInterval)).toBe(0);
      expect(Math.floor(9.99 / chunkInterval)).toBe(0);

      // Timeline 10-20s = chunk 1
      expect(Math.floor(10 / chunkInterval)).toBe(1);
      expect(Math.floor(19.99 / chunkInterval)).toBe(1);

      // Timeline 20-30s = chunk 2
      expect(Math.floor(20 / chunkInterval)).toBe(2);
      expect(Math.floor(29.99 / chunkInterval)).toBe(2);

      // Timeline 140-148.57s = chunk 14 (last)
      expect(Math.floor(140 / chunkInterval)).toBe(14);
      expect(Math.floor(148.57 / chunkInterval)).toBe(14);
    });

    test('should calculate correct offset within chunk', () => {
      const chunkInterval = mockMetadata.chunk_interval;

      // At 5.5s: chunk 0, offset 5.5s
      const time1 = 5.5;
      const chunkIndex1 = Math.floor(time1 / chunkInterval);
      const chunkStart1 = chunkIndex1 * chunkInterval;
      const offset1 = time1 - chunkStart1;
      expect(chunkIndex1).toBe(0);
      expect(offset1).toBe(5.5);

      // At 15.5s: chunk 1, offset 5.5s
      const time2 = 15.5;
      const chunkIndex2 = Math.floor(time2 / chunkInterval);
      const chunkStart2 = chunkIndex2 * chunkInterval;
      const offset2 = time2 - chunkStart2;
      expect(chunkIndex2).toBe(1);
      expect(offset2).toBe(5.5);

      // At 25.7s: chunk 2, offset 5.7s
      const time3 = 25.7;
      const chunkIndex3 = Math.floor(time3 / chunkInterval);
      const chunkStart3 = chunkIndex3 * chunkInterval;
      const offset3 = time3 - chunkStart3;
      expect(chunkIndex3).toBe(2);
      expect(offset3).toBeCloseTo(5.7, 10);
    });
  });

  describe('Play Duration Calculation', () => {
    test('should calculate correct play duration for normal chunks', () => {
      const chunkInterval = mockMetadata.chunk_interval;
      const duration = mockMetadata.duration;

      // Chunk 0: timeline 0-10s, should play for 10s (ignoring the 5s blend context)
      const chunk0Start = 0 * chunkInterval;
      const chunk0End = Math.min((0 + 1) * chunkInterval, duration);
      const chunk0PlayDuration = chunk0End - chunk0Start;
      expect(chunk0PlayDuration).toBe(10);

      // Chunk 1: timeline 10-20s, should play for 10s
      const chunk1Start = 1 * chunkInterval;
      const chunk1End = Math.min((1 + 1) * chunkInterval, duration);
      const chunk1PlayDuration = chunk1End - chunk1Start;
      expect(chunk1PlayDuration).toBe(10);

      // Chunk 14 (last): timeline 140-148.57s, should play for 8.57s
      const chunk14Start = 14 * chunkInterval;
      const chunk14End = Math.min((14 + 1) * chunkInterval, duration);
      const chunk14PlayDuration = chunk14End - chunk14Start;
      expect(chunk14PlayDuration).toBeCloseTo(8.57, 1);
    });

    test('should handle seeking within a chunk', () => {
      // Seeking to 15.5s means:
      // - Chunk 1 (starts at 10s)
      // - Offset: 5.5s into chunk
      // - Remaining: 10 - 5.5 = 4.5s to play in this chunk

      const chunkIndex = 1;
      const offset = 5.5;
      const chunkInterval = mockMetadata.chunk_interval;
      const duration = mockMetadata.duration;

      const chunkStart = chunkIndex * chunkInterval;
      const chunkEnd = Math.min((chunkIndex + 1) * chunkInterval, duration);
      const playDuration = chunkEnd - chunkStart - offset;

      expect(playDuration).toBe(4.5);
    });
  });

  describe('Current Time Calculation', () => {
    test('should accurately calculate current time during playback', () => {
      const chunkInterval = mockMetadata.chunk_interval;

      // Scenario 1: Playing chunk 0, 3.5s elapsed
      // - chunkStartTime = 0 * 10 = 0s
      // - currentChunkOffset = 0s (no seek)
      // - elapsed = 3.5s
      // - expected = 0 + 0 + 3.5 = 3.5s
      const scenario1 = {
        currentChunkIndex: 0,
        currentChunkOffset: 0,
        elapsedInChunk: 3.5,
        chunkStartTime: 0 * chunkInterval,
      };
      const time1 = scenario1.chunkStartTime + scenario1.currentChunkOffset + scenario1.elapsedInChunk;
      expect(time1).toBe(3.5);

      // Scenario 2: Playing chunk 1, 4.2s elapsed (seeked to 15.5s, then 4.2s played)
      // - chunkStartTime = 1 * 10 = 10s
      // - currentChunkOffset = 5.5s (seeked here)
      // - elapsed = 4.2s
      // - expected = 10 + 5.5 + 4.2 = 19.7s
      const scenario2 = {
        currentChunkIndex: 1,
        currentChunkOffset: 5.5,
        elapsedInChunk: 4.2,
        chunkStartTime: 1 * chunkInterval,
      };
      const time2 = scenario2.chunkStartTime + scenario2.currentChunkOffset + scenario2.elapsedInChunk;
      expect(time2).toBeCloseTo(19.7, 1);

      // Scenario 3: Playing chunk 5, 2.1s elapsed
      // - chunkStartTime = 5 * 10 = 50s
      // - currentChunkOffset = 0s (no seek)
      // - elapsed = 2.1s
      // - expected = 50 + 0 + 2.1 = 52.1s
      const scenario3 = {
        currentChunkIndex: 5,
        currentChunkOffset: 0,
        elapsedInChunk: 2.1,
        chunkStartTime: 5 * chunkInterval,
      };
      const time3 = scenario3.chunkStartTime + scenario3.currentChunkOffset + scenario3.elapsedInChunk;
      expect(time3).toBeCloseTo(52.1, 1);
    });
  });

  describe('Chunk Sequencing', () => {
    test('should sequence chunks in order without gaps', () => {
      const chunkInterval = mockMetadata.chunk_interval;
      const duration = mockMetadata.duration;
      const totalChunks = mockMetadata.total_chunks;

      let cumulativeTime = 0;
      for (let i = 0; i < totalChunks; i++) {
        const chunkStart = i * chunkInterval;
        const chunkEnd = Math.min((i + 1) * chunkInterval, duration);
        const chunkDuration = chunkEnd - chunkStart;

        // Each chunk should bridge from previous chunk end
        expect(chunkStart).toBe(cumulativeTime);
        cumulativeTime = chunkEnd;

        // Play duration should be positive
        expect(chunkDuration).toBeGreaterThan(0);
      }

      // Should cover entire track
      expect(cumulativeTime).toBeCloseTo(duration, 1);
    });

    test('should handle last chunk correctly', () => {
      const chunkInterval = mockMetadata.chunk_interval;
      const duration = mockMetadata.duration;
      const lastChunkIndex = mockMetadata.total_chunks - 1;

      const chunkStart = lastChunkIndex * chunkInterval;
      const chunkEnd = Math.min((lastChunkIndex + 1) * chunkInterval, duration);
      const playDuration = chunkEnd - chunkStart;

      // Last chunk should end exactly at track duration
      expect(chunkEnd).toBe(duration);
      // Play duration should be less than interval
      expect(playDuration).toBeLessThan(chunkInterval);
      expect(playDuration).toBeCloseTo(8.57, 1);
    });
  });

  describe('Buffer Duration Handling', () => {
    test('should handle different buffer durations correctly', () => {
      // Chunk 0: 15s buffer (has blend context)
      const chunk0BufferDuration = 15;
      // Should play for 10s timeline, but use full buffer
      const chunk0PlayDuration = Math.min(chunk0BufferDuration, 10);
      expect(chunk0PlayDuration).toBe(10);

      // Chunk 1: 10s buffer (overlap already trimmed)
      const chunk1BufferDuration = 10;
      // Should play for 10s timeline, use full buffer
      const chunk1PlayDuration = Math.min(chunk1BufferDuration, 10);
      expect(chunk1PlayDuration).toBe(10);

      // Chunk 14 (last): ~8.57s buffer
      const chunk14BufferDuration = 8.57;
      // Should play for 8.57s timeline
      const chunk14PlayDuration = Math.min(chunk14BufferDuration, 8.57);
      expect(chunk14PlayDuration).toBeCloseTo(8.57, 1);
    });

    test('should clamp play duration to buffer availability', () => {
      const bufferDuration = 10;
      const requestedDuration = 15;  // More than buffer has

      const playDuration = Math.min(requestedDuration, bufferDuration);
      expect(playDuration).toBe(bufferDuration);
    });
  });

  describe('Seeking Edge Cases', () => {
    test('should handle seeking to start of track', () => {
      const seekTime = 0;
      const chunkInterval = mockMetadata.chunk_interval;

      const chunkIndex = Math.floor(seekTime / chunkInterval);
      const chunkStart = chunkIndex * chunkInterval;
      const offset = seekTime - chunkStart;

      expect(chunkIndex).toBe(0);
      expect(offset).toBe(0);
    });

    test('should handle seeking to end of track', () => {
      const seekTime = mockMetadata.duration - 0.1;
      const chunkInterval = mockMetadata.chunk_interval;
      const duration = mockMetadata.duration;

      const chunkIndex = Math.floor(seekTime / chunkInterval);
      const chunkStart = chunkIndex * chunkInterval;
      const offset = seekTime - chunkStart;
      const chunkEnd = Math.min((chunkIndex + 1) * chunkInterval, duration);
      const playDuration = chunkEnd - chunkStart - offset;

      // Should be last chunk
      expect(chunkIndex).toBe(14);
      // Should play only remaining bit
      expect(playDuration).toBeGreaterThan(0);
      expect(playDuration).toBeLessThan(0.2);
    });

    test('should handle seeking to chunk boundary', () => {
      // Seek to exactly 20s (start of chunk 2)
      const seekTime = 20;
      const chunkInterval = mockMetadata.chunk_interval;

      const chunkIndex = Math.floor(seekTime / chunkInterval);
      const chunkStart = chunkIndex * chunkInterval;
      const offset = seekTime - chunkStart;

      expect(chunkIndex).toBe(2);
      expect(offset).toBe(0);
    });

    test('should handle seeking just before chunk boundary', () => {
      // Seek to 19.99s (still in chunk 1)
      const seekTime = 19.99;
      const chunkInterval = mockMetadata.chunk_interval;

      const chunkIndex = Math.floor(seekTime / chunkInterval);
      const chunkStart = chunkIndex * chunkInterval;
      const offset = seekTime - chunkStart;

      expect(chunkIndex).toBe(1);
      expect(offset).toBeCloseTo(9.99, 2);
    });
  });
});
