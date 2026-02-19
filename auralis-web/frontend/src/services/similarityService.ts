/**
 * Similarity Service (Phase 5b)
 * ~~~~~~~~~~~~~~~~~
 *
 * API client for 25D audio fingerprint similarity system
 *
 * Features:
 * - Find similar tracks
 * - Compare tracks
 * - Get similarity explanations
 * - Build K-NN graph
 * - Manage similarity system state
 *
 * Refactored using Service Factory Pattern (Phase 5b) to eliminate class boilerplate.
 */

import { createCrudService } from '../utils/serviceFactory';

const API_BASE = '/similarity';

export interface SimilarTrack {
  track_id: number;
  distance: number;
  similarity_score: number;
  title: string;
  artist: string;
  album: string;
  duration?: number;
  rank?: number;
}

export interface ComparisonResult {
  track_id1: number;
  track_id2: number;
  distance: number;
  similarity_score: number;
}

export interface DimensionContribution {
  dimension: string;
  contribution: number;
  value1: number;
  value2: number;
  difference: number;
}

export interface SimilarityExplanation {
  track_id1: number;
  track_id2: number;
  distance: number;
  similarity_score: number;
  top_differences: DimensionContribution[];
  all_contributions: DimensionContribution[];
}

export interface GraphStats {
  total_tracks: number;
  total_edges: number;
  k_neighbors: number;
  avg_distance: number;
  min_distance: number;
  max_distance: number;
  build_time_seconds: number;
}

export interface FitResult {
  fitted: boolean;
  total_fingerprints: number;
  message?: string;
}

// Create base service using factory with custom endpoints
const crudService = createCrudService<any, any>({
  custom: {
    findSimilar: (data) => `${API_BASE}/tracks/${data.trackId}/similar?limit=${data.limit}&use_graph=${data.useGraph}`,
    compareTracks: (data) => `${API_BASE}/tracks/${data.trackId1}/compare/${data.trackId2}`,
    explainSimilarity: (data) => `${API_BASE}/tracks/${data.trackId1}/explain/${data.trackId2}?top_n=${data.topN}`,
    buildGraph: (data) => `${API_BASE}/graph/build?k=${data.k}`,
    getGraphStats: `${API_BASE}/graph/stats`,
    fit: (data) => `${API_BASE}/fit?min_samples=${data.minSamples}`,
  },
});

/**
 * Find similar tracks to a given track
 *
 * @param trackId - Track ID to find similar tracks for
 * @param limit - Maximum number of similar tracks to return (default: 10)
 * @param useGraph - Use pre-computed K-NN graph (default: true, faster)
 * @returns List of similar tracks
 */
export async function findSimilar(
  trackId: number,
  limit: number = 10,
  useGraph: boolean = true
): Promise<SimilarTrack[]> {
  return crudService.custom('findSimilar', 'get', { trackId, limit, useGraph });
}

/**
 * Compare two tracks and get similarity score
 *
 * @param trackId1 - First track ID
 * @param trackId2 - Second track ID
 * @returns Comparison result with distance and similarity score
 */
export async function compareTracks(
  trackId1: number,
  trackId2: number
): Promise<ComparisonResult> {
  return crudService.custom('compareTracks', 'get', { trackId1, trackId2 });
}

/**
 * Get detailed similarity explanation between two tracks
 *
 * @param trackId1 - First track ID
 * @param trackId2 - Second track ID
 * @param topN - Number of top differences to highlight (default: 5)
 * @returns Detailed similarity explanation
 */
export async function explainSimilarity(
  trackId1: number,
  trackId2: number,
  topN: number = 5
): Promise<SimilarityExplanation> {
  return crudService.custom('explainSimilarity', 'get', { trackId1, trackId2, topN });
}

/**
 * Build K-NN similarity graph for fast queries
 *
 * @param k - Number of nearest neighbors per track (default: 10)
 * @returns Graph statistics
 */
export async function buildGraph(k: number = 10): Promise<GraphStats> {
  return crudService.custom('buildGraph', 'post', { k });
}

/**
 * Get current similarity graph statistics
 *
 * @returns Graph statistics or null if graph doesn't exist
 */
export async function getGraphStats(): Promise<GraphStats | null> {
  try {
    return await crudService.custom('getGraphStats', 'get', {});
  } catch (error: any) {
    // Handle 404 gracefully (graph doesn't exist)
    if (error.statusCode === 404) {
      return null;
    }
    throw error;
  }
}

/**
 * Fit similarity system (train normalizer on library)
 *
 * @param minSamples - Minimum number of fingerprints required (default: 10)
 * @returns Fit result
 */
export async function fit(minSamples: number = 10): Promise<FitResult> {
  return crudService.custom('fit', 'post', { minSamples });
}

/**
 * Check if similarity system is ready (fitted and has graph)
 *
 * @returns True if system is ready for queries
 */
export async function isReady(): Promise<boolean> {
  try {
    const stats = await getGraphStats();
    return stats !== null && stats.total_edges > 0;
  } catch {
    return false;
  }
}

// Export singleton object with all functions (maintains backward compatibility)
export const similarityService = {
  findSimilar,
  compareTracks,
  explainSimilarity,
  buildGraph,
  getGraphStats,
  fit,
  isReady,
};

export default similarityService;
