/**
 * MSE Streaming Service
 *
 * Handles chunk loading, caching, and progressive streaming for MSE playback.
 * Integrates with the backend multi-tier buffer system for intelligent pre-caching.
 *
 * Phase 3c Enhancement: Uses centralized error handling utilities for retry logic
 * and network resilience.
 */

import { retryWithBackoff, isRetryableError } from '../utils/errorHandling';

const API_BASE = '/api/mse_streaming';
const CHUNK_DURATION = 10; // seconds (reduced from 30s → 10s for Beta.9 Phase 2)

export interface ChunkMetadata {
  trackId: number;
  chunkIndex: number;
  preset: string;
  intensity: number;
  cacheTier?: string; // L1, L2, L3, or MISS
  sizeBytes?: number;
}

export interface TrackInfo {
  id: number;
  duration: number;
  totalChunks: number;
}

/**
 * Calculate total number of chunks for a track
 */
export function calculateTotalChunks(durationSeconds: number): number {
  return Math.ceil(durationSeconds / CHUNK_DURATION);
}

/**
 * Get chunk index for a given time position
 */
export function getChunkIndexForTime(timeSeconds: number): number {
  return Math.floor(timeSeconds / CHUNK_DURATION);
}

/**
 * Get time range for a chunk
 */
export function getChunkTimeRange(chunkIndex: number): { start: number; end: number } {
  return {
    start: chunkIndex * CHUNK_DURATION,
    end: (chunkIndex + 1) * CHUNK_DURATION,
  };
}

/**
 * Load a single chunk from the backend with automatic retry on network errors
 */
export async function loadChunk(
  trackId: number,
  chunkIndex: number,
  preset: string,
  intensity: number
): Promise<{ data: ArrayBuffer; metadata: ChunkMetadata }> {
  const url = `${API_BASE}/chunk/${trackId}/${chunkIndex}?preset=${preset}&intensity=${intensity}`;

  console.log(`📡 Fetching chunk ${chunkIndex} (preset: ${preset})`);

  // Use retry logic for network resilience
  const response = await retryWithBackoff(
    async () => {
      const res = await fetch(url, {
        headers: {
          'Accept': 'audio/webm',
        },
      });

      if (!res.ok) {
        throw new Error(`Failed to load chunk ${chunkIndex}: ${res.status} ${res.statusText}`);
      }

      return res;
    },
    {
      maxRetries: 3,
      initialDelayMs: 100,
      shouldRetry: isRetryableError,
    }
  );

  const arrayBuffer = await response.arrayBuffer();
  const cacheTier = response.headers.get('X-Cache-Tier') || undefined;

  const metadata: ChunkMetadata = {
    trackId,
    chunkIndex,
    preset,
    intensity,
    cacheTier,
    sizeBytes: arrayBuffer.byteLength,
  };

  if (cacheTier) {
    console.log(`💾 Chunk ${chunkIndex} from ${cacheTier} cache (${(arrayBuffer.byteLength / 1024).toFixed(1)} KB)`);
  } else {
    console.log(`⚡ Chunk ${chunkIndex} processed on-demand (${(arrayBuffer.byteLength / 1024).toFixed(1)} KB)`);
  }

  return { data: arrayBuffer, metadata };
}

/**
 * Preload multiple chunks in parallel
 */
export async function preloadChunks(
  trackId: number,
  chunkIndices: number[],
  preset: string,
  intensity: number
): Promise<Map<number, ArrayBuffer>> {
  console.log(`🚀 Preloading ${chunkIndices.length} chunks in parallel`);

  const promises = chunkIndices.map(async (index) => {
    try {
      const { data } = await loadChunk(trackId, index, preset, intensity);
      return { index, data };
    } catch (err) {
      console.warn(`Failed to preload chunk ${index}:`, err);
      return { index, data: null };
    }
  });

  const results = await Promise.all(promises);

  const chunks = new Map<number, ArrayBuffer>();
  results.forEach(({ index, data }) => {
    if (data) {
      chunks.set(index, data);
    }
  });

  console.log(`✅ Preloaded ${chunks.size}/${chunkIndices.length} chunks successfully`);
  return chunks;
}

/**
 * Get chunks to prefetch based on current position
 */
export function getChunksToPrefetch(
  currentChunk: number,
  totalChunks: number,
  prefetchCount: number = 2
): number[] {
  const chunks: number[] = [];

  for (let i = 1; i <= prefetchCount; i++) {
    const nextChunk = currentChunk + i;
    if (nextChunk < totalChunks) {
      chunks.push(nextChunk);
    }
  }

  return chunks;
}

// Retry logic moved to centralized errorHandling utilities (Phase 3c)
