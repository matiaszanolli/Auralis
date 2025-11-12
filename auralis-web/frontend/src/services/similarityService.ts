/**
 * Similarity Service
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
 */

import { get, post } from '../utils/apiRequest';

const API_BASE = '/similarity';

/**
 * Helper to build URL with query parameters
 */
function buildUrl(path: string, params?: Record<string, string | number | boolean>): string {
  if (!params) return path;
  const searchParams = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    searchParams.append(key, String(value));
  });
  return `${path}?${searchParams.toString()}`;
}

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

class SimilarityService {
  /**
   * Find similar tracks to a given track
   *
   * @param trackId - Track ID to find similar tracks for
   * @param limit - Maximum number of similar tracks to return (default: 10)
   * @param useGraph - Use pre-computed K-NN graph (default: true, faster)
   * @returns List of similar tracks
   */
  async findSimilar(
    trackId: number,
    limit: number = 10,
    useGraph: boolean = true
  ): Promise<SimilarTrack[]> {
    const url = buildUrl(`${API_BASE}/tracks/${trackId}/similar`, { limit, use_graph: useGraph });
    return get(url);
  }

  /**
   * Compare two tracks and get similarity score
   *
   * @param trackId1 - First track ID
   * @param trackId2 - Second track ID
   * @returns Comparison result with distance and similarity score
   */
  async compareTracks(
    trackId1: number,
    trackId2: number
  ): Promise<ComparisonResult> {
    return get(`${API_BASE}/tracks/${trackId1}/compare/${trackId2}`);
  }

  /**
   * Get detailed similarity explanation between two tracks
   *
   * @param trackId1 - First track ID
   * @param trackId2 - Second track ID
   * @param topN - Number of top differences to highlight (default: 5)
   * @returns Detailed similarity explanation
   */
  async explainSimilarity(
    trackId1: number,
    trackId2: number,
    topN: number = 5
  ): Promise<SimilarityExplanation> {
    const url = buildUrl(`${API_BASE}/tracks/${trackId1}/explain/${trackId2}`, { top_n: topN });
    return get(url);
  }

  /**
   * Build K-NN similarity graph for fast queries
   *
   * @param k - Number of nearest neighbors per track (default: 10)
   * @returns Graph statistics
   */
  async buildGraph(k: number = 10): Promise<GraphStats> {
    const url = buildUrl(`${API_BASE}/graph/build`, { k });
    return post(url, {});
  }

  /**
   * Get current similarity graph statistics
   *
   * @returns Graph statistics or null if graph doesn't exist
   */
  async getGraphStats(): Promise<GraphStats | null> {
    try {
      return await get(`${API_BASE}/graph/stats`);
    } catch (error: any) {
      // Handle 404 gracefully (graph doesn't exist)
      if (error.status === 404) {
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
  async fit(minSamples: number = 10): Promise<FitResult> {
    const url = buildUrl(`${API_BASE}/fit`, { min_samples: minSamples });
    return post(url, {});
  }

  /**
   * Check if similarity system is ready (fitted and has graph)
   *
   * @returns True if system is ready for queries
   */
  async isReady(): Promise<boolean> {
    try {
      const stats = await this.getGraphStats();
      return stats !== null && stats.total_edges > 0;
    } catch {
      return false;
    }
  }
}

// Export singleton instance
export const similarityService = new SimilarityService();
export default similarityService;
