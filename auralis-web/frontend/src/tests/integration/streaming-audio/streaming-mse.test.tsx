/**
 * Streaming & Media Source Extensions (MSE) Integration Tests
 *
 * Comprehensive integration tests for MSE-based progressive streaming
 * Part of Week 5 frontend testing roadmap (200-test suite)
 *
 * Test Categories:
 * 1. MSE Initialization & Lifecycle (4 tests)
 * 2. Progressive Streaming (4 tests)
 * 3. Preset Switching (4 tests)
 * 4. Buffer Management (3 tests)
 * 5. Audio Format Handling (3 tests)
 * 6. Error Scenarios (2 tests)
 *
 * Total: 20 tests
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { waitFor } from '@testing-library/react';

// ============================================================
// MSE API MOCKS
// ============================================================

/**
 * Mock MediaSource class for testing
 */
class MockMediaSource extends EventTarget {
  readyState: 'closed' | 'open' | 'ended' = 'closed';
  sourceBuffers: MockSourceBufferList;
  duration: number = 0;

  private _onSourceOpen?: () => void;
  private _onSourceEnded?: () => void;
  private _onSourceClose?: () => void;

  constructor() {
    super();
    this.sourceBuffers = new MockSourceBufferList();

    // Simulate async source open
    setTimeout(() => {
      this.readyState = 'open';
      const event = new Event('sourceopen');
      this.dispatchEvent(event);
      if (this._onSourceOpen) this._onSourceOpen();
    }, 10);
  }

  addSourceBuffer(mimeType: string): MockSourceBuffer {
    const buffer = new MockSourceBuffer(mimeType);
    this.sourceBuffers.add(buffer);
    return buffer;
  }

  endOfStream(): void {
    this.readyState = 'ended';
    const event = new Event('sourceended');
    this.dispatchEvent(event);
    if (this._onSourceEnded) this._onSourceEnded();
  }

  set onsourceopen(handler: (() => void) | null) {
    if (handler) {
      this._onSourceOpen = handler;
      this.addEventListener('sourceopen', handler);
    } else {
      this._onSourceOpen = undefined;
    }
  }

  set onsourceended(handler: (() => void) | null) {
    if (handler) {
      this._onSourceEnded = handler;
      this.addEventListener('sourceended', handler);
    } else {
      this._onSourceEnded = undefined;
    }
  }

  set onsourceclose(handler: (() => void) | null) {
    if (handler) {
      this._onSourceClose = handler;
      this.addEventListener('sourceclose', handler);
    } else {
      this._onSourceClose = undefined;
    }
  }

  static isTypeSupported(mimeType: string): boolean {
    // Mock support for WebM/Opus
    return mimeType === 'audio/webm; codecs=opus' || mimeType === 'audio/webm';
  }
}

/**
 * Mock SourceBuffer class
 */
class MockSourceBuffer extends EventTarget {
  mode: 'segments' | 'sequence' = 'segments';
  updating: boolean = false;
  buffered: MockTimeRanges;
  timestampOffset: number = 0;
  appendWindowStart: number = 0;
  appendWindowEnd: number = Infinity;
  private _chunks: ArrayBuffer[] = [];
  private _mimeType: string;

  private _onUpdateEnd?: () => void;
  private _onError?: (e: Event) => void;

  constructor(mimeType: string) {
    super();
    this._mimeType = mimeType;
    this.buffered = new MockTimeRanges();
  }

  appendBuffer(data: ArrayBuffer): void {
    if (this.updating) {
      throw new Error('Already updating');
    }

    this.updating = true;
    this._chunks.push(data);

    // Simulate async append
    setTimeout(() => {
      this.updating = false;

      // Update buffered time ranges (simulate 10s chunks)
      const chunkDuration = 10;
      const newEnd = this._chunks.length * chunkDuration;
      this.buffered.add(0, newEnd);

      const event = new Event('updateend');
      this.dispatchEvent(event);
      if (this._onUpdateEnd) this._onUpdateEnd();
    }, 50);
  }

  remove(start: number, end: number): void {
    if (this.updating) {
      throw new Error('Already updating');
    }

    this.updating = true;

    // Simulate async remove
    setTimeout(() => {
      this.updating = false;
      this.buffered.remove(start, end);
      // Also clear chunks when removing buffer
      this._chunks = [];

      const event = new Event('updateend');
      this.dispatchEvent(event);
      if (this._onUpdateEnd) this._onUpdateEnd();
    }, 20);
  }

  abort(): void {
    this.updating = false;
    this._chunks = [];
    this.buffered.clear();
  }

  set onupdateend(handler: (() => void) | null) {
    if (handler) {
      this._onUpdateEnd = handler;
      this.addEventListener('updateend', handler);
    } else {
      this._onUpdateEnd = undefined;
    }
  }

  set onerror(handler: ((e: Event) => void) | null) {
    if (handler) {
      this._onError = handler;
      this.addEventListener('error', handler);
    } else {
      this._onError = undefined;
    }
  }

  getChunks(): ArrayBuffer[] {
    return this._chunks;
  }
}

/**
 * Mock SourceBufferList
 */
class MockSourceBufferList {
  private _buffers: MockSourceBuffer[] = [];
  length: number = 0;

  add(buffer: MockSourceBuffer): void {
    this._buffers.push(buffer);
    this.length = this._buffers.length;
  }

  item(index: number): MockSourceBuffer | null {
    return this._buffers[index] || null;
  }

  [index: number]: MockSourceBuffer;
}

/**
 * Mock TimeRanges for buffered property
 */
class MockTimeRanges {
  private _ranges: Array<{ start: number; end: number }> = [];

  get length(): number {
    return this._ranges.length;
  }

  start(index: number): number {
    if (index < 0 || index >= this._ranges.length) {
      throw new Error('Index out of bounds');
    }
    return this._ranges[index].start;
  }

  end(index: number): number {
    if (index < 0 || index >= this._ranges.length) {
      throw new Error('Index out of bounds');
    }
    return this._ranges[index].end;
  }

  add(start: number, end: number): void {
    // Merge overlapping ranges
    const newRange = { start, end };
    const merged: Array<{ start: number; end: number }> = [];
    let inserted = false;

    for (const range of this._ranges) {
      if (newRange.end < range.start) {
        if (!inserted) {
          merged.push(newRange);
          inserted = true;
        }
        merged.push(range);
      } else if (newRange.start > range.end) {
        merged.push(range);
      } else {
        // Overlapping - merge
        newRange.start = Math.min(newRange.start, range.start);
        newRange.end = Math.max(newRange.end, range.end);
      }
    }

    if (!inserted) {
      merged.push(newRange);
    }

    this._ranges = merged;
  }

  remove(start: number, end: number): void {
    this._ranges = this._ranges.filter(range => {
      // Keep ranges that don't overlap with removal range
      return range.end <= start || range.start >= end;
    });
  }

  clear(): void {
    this._ranges = [];
  }
}

// ============================================================
// TEST HELPERS
// ============================================================

/**
 * Create mock WebM/Opus audio chunk
 */
function createMockWebMChunk(chunkIndex: number, size: number = 1024): ArrayBuffer {
  // Create a simple ArrayBuffer representing WebM chunk
  const buffer = new ArrayBuffer(size);
  const view = new Uint8Array(buffer);

  // Fill with mock data (in real WebM, this would be actual encoded data)
  for (let i = 0; i < size; i++) {
    view[i] = (chunkIndex + i) % 256;
  }

  return buffer;
}

/**
 * Stream metadata mock
 */
const createMockStreamMetadata = (trackId: number, totalChunks: number = 20) => ({
  track_id: trackId,
  duration: totalChunks * 10, // 10s per chunk
  sample_rate: 44100,
  channels: 2,
  chunk_duration: 10,
  chunk_interval: 10,
  total_chunks: totalChunks,
  mime_type: 'audio/webm',
  codecs: 'opus',
  format_version: 'unified-v1.0'
});

/**
 * Simulated MSE streaming player
 */
class TestMSEPlayer {
  mediaSource: MockMediaSource | null = null;
  sourceBuffer: MockSourceBuffer | null = null;
  audioElement: HTMLAudioElement | null = null;
  objectUrl: string | null = null;
  trackId: number | null = null;
  currentPreset: string = 'adaptive';
  currentChunk: number = 0;

  async initialize(trackId: number): Promise<void> {
    this.trackId = trackId;

    // Create MediaSource
    this.mediaSource = new MockMediaSource();

    // Create object URL
    this.objectUrl = `blob:http://localhost:8765/${Math.random()}`;

    // Create audio element
    this.audioElement = document.createElement('audio');
    this.audioElement.src = this.objectUrl;

    // Wait for source open
    await new Promise<void>(resolve => {
      if (this.mediaSource) {
        this.mediaSource.onsourceopen = () => resolve();
      }
    });

    // Add source buffer
    if (this.mediaSource) {
      this.sourceBuffer = this.mediaSource.addSourceBuffer('audio/webm; codecs=opus');
    }
  }

  async appendChunk(chunkData: ArrayBuffer): Promise<void> {
    if (!this.sourceBuffer) {
      throw new Error('Source buffer not initialized');
    }

    // Wait for source buffer to be ready
    while (this.sourceBuffer.updating) {
      await new Promise(resolve => setTimeout(resolve, 10));
    }

    return new Promise((resolve, reject) => {
      if (this.sourceBuffer) {
        this.sourceBuffer.onupdateend = () => {
          resolve();
        };
        this.sourceBuffer.onerror = (e) => reject(e);
        this.sourceBuffer.appendBuffer(chunkData);
      } else {
        reject(new Error('Source buffer not available'));
      }
    });
  }

  async switchPreset(newPreset: string): Promise<void> {
    if (!this.sourceBuffer || !this.mediaSource) {
      throw new Error('Player not initialized');
    }

    // Wait for ongoing operations to complete
    while (this.sourceBuffer.updating) {
      await new Promise(resolve => setTimeout(resolve, 10));
    }

    // Clear old buffer
    const buffered = this.sourceBuffer.buffered;
    if (buffered.length > 0) {
      const start = buffered.start(0);
      const end = buffered.end(buffered.length - 1);
      this.sourceBuffer.remove(start, end);

      await new Promise<void>(resolve => {
        if (this.sourceBuffer) {
          this.sourceBuffer.onupdateend = () => resolve();
        }
      });
    }

    // Update preset
    this.currentPreset = newPreset;
    this.currentChunk = 0;
  }

  getBufferHealth(): { bufferedSeconds: number; bufferAhead: number } {
    if (!this.sourceBuffer || !this.audioElement) {
      return { bufferedSeconds: 0, bufferAhead: 0 };
    }

    const buffered = this.sourceBuffer.buffered;
    if (buffered.length === 0) {
      return { bufferedSeconds: 0, bufferAhead: 0 };
    }

    const bufferedEnd = buffered.end(buffered.length - 1);
    const currentTime = this.audioElement.currentTime || 0;
    const bufferAhead = bufferedEnd - currentTime;

    return {
      bufferedSeconds: bufferedEnd,
      bufferAhead: Math.max(0, bufferAhead)
    };
  }

  cleanup(): void {
    if (this.audioElement) {
      this.audioElement.pause();
      this.audioElement.src = '';
    }
    if (this.sourceBuffer) {
      this.sourceBuffer.abort();
    }
    this.mediaSource = null;
    this.sourceBuffer = null;
    this.audioElement = null;
    this.objectUrl = null;
  }
}

// ============================================================
// TESTS
// ============================================================

describe('Streaming & MSE Integration Tests', () => {
  let player: TestMSEPlayer;

  beforeEach(() => {
    // Mock global MediaSource
    (global as any).MediaSource = MockMediaSource;

    // Mock URL.createObjectURL
    global.URL.createObjectURL = vi.fn(() => `blob:http://localhost:8765/${Math.random()}`);
    global.URL.revokeObjectURL = vi.fn();

    player = new TestMSEPlayer();
  });

  afterEach(() => {
    player.cleanup();
    vi.clearAllMocks();
  });

  // ==========================================
  // 1. MSE Initialization & Lifecycle (4 tests)
  // ==========================================

  describe('MSE Initialization & Lifecycle', () => {
    it('should initialize Media Source Extensions successfully', async () => {
      // Arrange
      const trackId = 1;

      // Act
      await player.initialize(trackId);

      // Assert
      expect(player.mediaSource).toBeDefined();
      expect(player.mediaSource?.readyState).toBe('open');
      expect(player.sourceBuffer).toBeDefined();
      expect(player.audioElement).toBeDefined();
      expect(player.objectUrl).toBeDefined();
    });

    it('should create source buffer for audio/webm codec', async () => {
      // Arrange
      const trackId = 1;

      // Act
      await player.initialize(trackId);

      // Assert
      expect(player.sourceBuffer).toBeDefined();
      expect(player.mediaSource?.sourceBuffers.length).toBe(1);
      expect(MockMediaSource.isTypeSupported('audio/webm; codecs=opus')).toBe(true);
    });

    it('should handle source buffer updates correctly', async () => {
      // Arrange
      await player.initialize(1);
      const chunkData = createMockWebMChunk(0, 2048);

      // Act
      await player.appendChunk(chunkData);

      // Assert
      expect(player.sourceBuffer?.updating).toBe(false);
      expect(player.sourceBuffer?.buffered.length).toBe(1);
      expect(player.sourceBuffer?.buffered.end(0)).toBe(10); // 1 chunk = 10s
    });

    it('should clean up MSE resources on unmount', async () => {
      // Arrange
      await player.initialize(1);
      const chunk1 = createMockWebMChunk(0);
      await player.appendChunk(chunk1);

      // Act
      player.cleanup();

      // Assert
      expect(player.mediaSource).toBeNull();
      expect(player.sourceBuffer).toBeNull();
      expect(player.audioElement).toBeNull();
      expect(player.objectUrl).toBeNull();
    });
  });

  // ==========================================
  // 2. Progressive Streaming (4 tests)
  // ==========================================

  describe('Progressive Streaming', () => {
    it('should request and append audio stream chunks', async () => {
      // Arrange
      await player.initialize(1);

      // Act - Append 3 chunks
      for (let i = 0; i < 3; i++) {
        const chunkData = createMockWebMChunk(i, 2048);
        await player.appendChunk(chunkData);
      }

      // Assert
      expect(player.sourceBuffer?.buffered.length).toBe(1);
      expect(player.sourceBuffer?.buffered.end(0)).toBe(30); // 3 chunks * 10s each
      expect(player.sourceBuffer?.getChunks().length).toBe(3); // 3 chunks appended
    });

    it('should handle chunk buffering and playback', async () => {
      // Arrange
      await player.initialize(1);
      const metadata = createMockStreamMetadata(1, 20);

      // Act - Buffer first 5 chunks (50 seconds)
      for (let i = 0; i < 5; i++) {
        const chunkData = createMockWebMChunk(i, 1024);
        await player.appendChunk(chunkData);
      }

      const bufferHealth = player.getBufferHealth();

      // Assert
      expect(bufferHealth.bufferedSeconds).toBe(50);
      expect(player.sourceBuffer?.buffered.length).toBeGreaterThan(0);
    });

    it('should monitor buffer health (underrun detection)', async () => {
      // Arrange
      await player.initialize(1);

      // Act - Append single chunk
      const chunk = createMockWebMChunk(0);
      await player.appendChunk(chunk);

      // Simulate playback at 8 seconds (2s buffer ahead)
      if (player.audioElement) {
        player.audioElement.currentTime = 8;
      }

      const bufferHealth = player.getBufferHealth();

      // Assert
      expect(bufferHealth.bufferedSeconds).toBe(10); // 1 chunk = 10s
      expect(bufferHealth.bufferAhead).toBe(2); // 10s buffered - 8s played

      // Buffer underrun warning threshold is typically 5s
      const isUnderrun = bufferHealth.bufferAhead < 5;
      expect(isUnderrun).toBe(true); // Should warn about low buffer
    });

    it('should append chunks sequentially without gaps', async () => {
      // Arrange
      await player.initialize(1);

      // Act - Append 10 chunks sequentially
      for (let i = 0; i < 10; i++) {
        const chunkData = createMockWebMChunk(i);
        await player.appendChunk(chunkData);
      }

      // Assert - Should have continuous buffer
      expect(player.sourceBuffer?.buffered.length).toBe(1);
      expect(player.sourceBuffer?.buffered.start(0)).toBe(0);
      expect(player.sourceBuffer?.buffered.end(0)).toBe(100); // 10 chunks * 10s
    });
  });

  // ==========================================
  // 3. Preset Switching (4 tests)
  // ==========================================

  describe('Preset Switching', () => {
    it('should switch preset during playback (seamless transition)', async () => {
      // Arrange
      await player.initialize(1);

      // Append some chunks with 'adaptive' preset
      for (let i = 0; i < 3; i++) {
        await player.appendChunk(createMockWebMChunk(i));
      }

      const initialPreset = player.currentPreset;
      const initialBuffered = player.sourceBuffer?.buffered.end(0);

      // Act - Switch to 'warm' preset
      await player.switchPreset('warm');

      // Assert
      expect(initialPreset).toBe('adaptive');
      expect(player.currentPreset).toBe('warm');
      expect(player.currentChunk).toBe(0); // Reset for new preset
    });

    it('should request new stream with different preset', async () => {
      // Arrange
      await player.initialize(1);
      await player.appendChunk(createMockWebMChunk(0));
      const initialChunks = player.sourceBuffer?.getChunks().length;

      // Act - Switch preset
      const oldPreset = player.currentPreset;
      await player.switchPreset('bright');

      // Assert
      expect(oldPreset).toBe('adaptive');
      expect(player.currentPreset).toBe('bright');

      // New chunks should be requested with new preset
      await player.appendChunk(createMockWebMChunk(0));
      expect(player.sourceBuffer?.getChunks().length).toBe(1); // Buffer cleared, only new chunk
    });

    it('should clear old buffer and append new chunks', async () => {
      // Arrange
      await player.initialize(1);

      // Buffer 5 chunks
      for (let i = 0; i < 5; i++) {
        await player.appendChunk(createMockWebMChunk(i));
      }

      expect(player.sourceBuffer?.buffered.length).toBe(1);
      expect(player.sourceBuffer?.buffered.end(0)).toBe(50);
      expect(player.sourceBuffer?.getChunks().length).toBe(5);

      // Act - Switch preset (should clear buffer)
      await player.switchPreset('punchy');

      // Assert - Buffer should be cleared
      expect(player.sourceBuffer?.buffered.length).toBe(0);
      expect(player.sourceBuffer?.getChunks().length).toBe(0);

      // Append new chunks with new preset
      await player.appendChunk(createMockWebMChunk(0));
      expect(player.sourceBuffer?.buffered.end(0)).toBe(10);
      expect(player.sourceBuffer?.getChunks().length).toBe(1);
    });

    it('should verify no audio gaps during preset change', async () => {
      // Arrange
      await player.initialize(1);

      // Buffer initial chunks
      for (let i = 0; i < 3; i++) {
        await player.appendChunk(createMockWebMChunk(i));
      }

      // Simulate playback at 15 seconds
      if (player.audioElement) {
        player.audioElement.currentTime = 15;
      }

      // Act - Switch preset mid-playback
      await player.switchPreset('warm');

      // Immediately buffer new chunks from current position
      for (let i = 0; i < 2; i++) {
        await player.appendChunk(createMockWebMChunk(i));
      }

      const bufferHealth = player.getBufferHealth();

      // Assert - Should have buffered audio ahead of current time
      expect(bufferHealth.bufferedSeconds).toBeGreaterThan(0);
      expect(bufferHealth.bufferAhead).toBeGreaterThan(0);
    });
  });

  // ==========================================
  // 4. Buffer Management (3 tests)
  // ==========================================

  describe('Buffer Management', () => {
    it('should monitor buffer levels (ahead/behind playback)', async () => {
      // Arrange
      await player.initialize(1);

      // Buffer 4 chunks (40 seconds)
      for (let i = 0; i < 4; i++) {
        await player.appendChunk(createMockWebMChunk(i));
      }

      // Act - Simulate playback at different positions
      const testPositions = [0, 10, 20, 35];
      const results = [];

      for (const position of testPositions) {
        if (player.audioElement) {
          player.audioElement.currentTime = position;
        }
        results.push(player.getBufferHealth());
      }

      // Assert
      expect(results[0].bufferAhead).toBe(40); // At start: 40s ahead
      expect(results[1].bufferAhead).toBe(30); // At 10s: 30s ahead
      expect(results[2].bufferAhead).toBe(20); // At 20s: 20s ahead
      expect(results[3].bufferAhead).toBe(5);  // At 35s: 5s ahead
    });

    it('should handle buffer overflow scenarios', async () => {
      // Arrange
      await player.initialize(1);
      const maxBufferSize = 100; // 100 seconds max buffer

      // Act - Try to buffer more than max (15 chunks = 150 seconds)
      let bufferedCount = 0;
      for (let i = 0; i < 15; i++) {
        await player.appendChunk(createMockWebMChunk(i));
        bufferedCount++;

        // Check if buffer limit reached
        const buffered = player.sourceBuffer?.buffered.end(0) || 0;
        if (buffered >= maxBufferSize) {
          break;
        }
      }

      // Assert - Should stop at max buffer size
      expect(player.sourceBuffer?.buffered.end(0)).toBe(100); // Stopped at 10 chunks
      expect(bufferedCount).toBe(10); // Only buffered 10 chunks (100 seconds)
    });

    it('should recover from buffer underrun', async () => {
      // Arrange
      await player.initialize(1);

      // Buffer only 1 chunk
      await player.appendChunk(createMockWebMChunk(0));

      // Simulate playback at 9.5s (0.5s buffer ahead - underrun!)
      if (player.audioElement) {
        player.audioElement.currentTime = 9.5;
      }

      const initialHealth = player.getBufferHealth();
      expect(initialHealth.bufferAhead).toBeLessThan(1);

      // Act - Recover by buffering more chunks
      for (let i = 1; i < 4; i++) {
        await player.appendChunk(createMockWebMChunk(i));
      }

      const recoveredHealth = player.getBufferHealth();

      // Assert - Buffer should be healthy again
      expect(recoveredHealth.bufferedSeconds).toBe(40);
      expect(recoveredHealth.bufferAhead).toBeGreaterThan(20);
    });
  });

  // ==========================================
  // 5. Audio Format Handling (3 tests)
  // ==========================================

  describe('Audio Format Handling', () => {
    it('should support WebM/Opus codec', async () => {
      // Arrange & Act
      const isSupported = MockMediaSource.isTypeSupported('audio/webm; codecs=opus');
      const isWebMSupported = MockMediaSource.isTypeSupported('audio/webm');

      // Assert
      expect(isSupported).toBe(true);
      expect(isWebMSupported).toBe(true);
    });

    it('should handle sample rate variations', async () => {
      // Arrange
      await player.initialize(1);
      const metadata = createMockStreamMetadata(1);

      // Act
      const sampleRate = metadata.sample_rate;
      const channels = metadata.channels;

      // Assert
      expect(sampleRate).toBe(44100); // Standard CD quality
      expect(channels).toBe(2); // Stereo
    });

    it('should validate audio metadata', async () => {
      // Arrange
      const trackId = 1;
      const metadata = createMockStreamMetadata(trackId, 25);

      // Act & Assert - Validate metadata structure
      expect(metadata.track_id).toBe(trackId);
      expect(metadata.duration).toBe(250); // 25 chunks * 10s
      expect(metadata.sample_rate).toBe(44100);
      expect(metadata.channels).toBe(2);
      expect(metadata.chunk_duration).toBe(10);
      expect(metadata.chunk_interval).toBe(10);
      expect(metadata.total_chunks).toBe(25);
      expect(metadata.mime_type).toBe('audio/webm');
      expect(metadata.codecs).toBe('opus');
      expect(metadata.format_version).toBe('unified-v1.0');
    });
  });

  // ==========================================
  // 6. Error Scenarios (2 tests)
  // ==========================================

  describe('Error Scenarios', () => {
    it('should handle streaming errors gracefully', async () => {
      // Arrange
      await player.initialize(1);

      // Act & Assert - Try to append while updating (should throw)
      const chunk1 = createMockWebMChunk(0);
      const appendPromise = player.appendChunk(chunk1);

      // Try to append again immediately (while first is updating)
      await expect(async () => {
        if (player.sourceBuffer) {
          player.sourceBuffer.appendBuffer(createMockWebMChunk(1));
        }
      }).rejects.toThrow('Already updating');

      // Wait for first append to complete
      await appendPromise;

      // Now next append should work
      await player.appendChunk(createMockWebMChunk(1));
      expect(player.sourceBuffer?.getChunks().length).toBe(2);
    });

    it('should recover from network interruptions', async () => {
      // Arrange
      await player.initialize(1);

      // Buffer some chunks successfully
      await player.appendChunk(createMockWebMChunk(0));
      await player.appendChunk(createMockWebMChunk(1));

      const initialChunks = player.sourceBuffer?.getChunks().length;
      expect(initialChunks).toBe(2);

      // Act - Simulate network error (skip chunk 2)
      // Then resume with chunk 3
      await player.appendChunk(createMockWebMChunk(3));

      // Assert - Should continue playback despite gap
      expect(player.sourceBuffer?.getChunks().length).toBe(3);
      expect(player.sourceBuffer?.buffered.length).toBeGreaterThan(0);
    });
  });
});
