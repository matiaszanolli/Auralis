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

const API_BASE = 'http://localhost:8765/api/similarity';

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
    try {
      const response = await fetch(
        `${API_BASE}/tracks/${trackId}/similar?limit=${limit}&use_graph=${useGraph}`
      );

      if (!response.ok) {
        throw new Error(`Failed to find similar tracks: ${response.statusText}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Error finding similar tracks:', error);
      throw error;
    }
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
    try {
      const response = await fetch(
        `${API_BASE}/tracks/${trackId1}/compare/${trackId2}`
      );

      if (!response.ok) {
        throw new Error(`Failed to compare tracks: ${response.statusText}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Error comparing tracks:', error);
      throw error;
    }
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
    try {
      const response = await fetch(
        `${API_BASE}/tracks/${trackId1}/explain/${trackId2}?top_n=${topN}`
      );

      if (!response.ok) {
        throw new Error(`Failed to explain similarity: ${response.statusText}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Error explaining similarity:', error);
      throw error;
    }
  }

  /**
   * Build K-NN similarity graph for fast queries
   *
   * @param k - Number of nearest neighbors per track (default: 10)
   * @returns Graph statistics
   */
  async buildGraph(k: number = 10): Promise<GraphStats> {
    try {
      const response = await fetch(
        `${API_BASE}/graph/build?k=${k}`,
        { method: 'POST' }
      );

      if (!response.ok) {
        throw new Error(`Failed to build graph: ${response.statusText}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Error building graph:', error);
      throw error;
    }
  }

  /**
   * Get current similarity graph statistics
   *
   * @returns Graph statistics or null if graph doesn't exist
   */
  async getGraphStats(): Promise<GraphStats | null> {
    try {
      const response = await fetch(`${API_BASE}/graph/stats`);

      if (!response.ok) {
        if (response.status === 404) {
          return null; // Graph doesn't exist
        }
        throw new Error(`Failed to get graph stats: ${response.statusText}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Error getting graph stats:', error);
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
    try {
      const response = await fetch(
        `${API_BASE}/fit?min_samples=${minSamples}`,
        { method: 'POST' }
      );

      if (!response.ok) {
        throw new Error(`Failed to fit similarity system: ${response.statusText}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Error fitting similarity system:', error);
      throw error;
    }
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
    } catch (error) {
      console.error('Error checking similarity system status:', error);
      return false;
    }
  }
}

// Export singleton instance
export const similarityService = new SimilarityService();
export default similarityService;
