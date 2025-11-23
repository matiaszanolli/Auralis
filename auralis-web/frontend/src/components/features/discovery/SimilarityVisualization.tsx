/**
 * SimilarityVisualization Component
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Visualizes similarity between two tracks with dimension contributions
 *
 * Features:
 * - Overall similarity score with radial progress
 * - Top dimension differences highlighted
 * - Bar chart showing contribution of each dimension
 * - Detailed dimension values comparison
 */

import React, { useState, useEffect } from 'react';
import { Box } from '@mui/material';
import similarityService, { SimilarityExplanation } from '../../../services/similarityService';
import {
  SimilarityLoadingState,
  SimilarityErrorState,
  SimilarityEmptyState,
} from './SimilarityVisualizationStates';
import SimilarityOverallScore from './SimilarityOverallScore';
import SimilarityTopDifferences from './SimilarityTopDifferences';
import SimilarityAllDimensions from './SimilarityAllDimensions';

interface SimilarityVisualizationProps {
  /** First track ID */
  trackId1: number | null;
  /** Second track ID */
  trackId2: number | null;
  /** Number of top differences to highlight (default: 5) */
  topN?: number;
}

const SimilarityVisualization: React.FC<SimilarityVisualizationProps> = ({
  trackId1,
  trackId2,
  topN = 5,
}) => {
  const [explanation, setExplanation] = useState<SimilarityExplanation | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load explanation when track IDs change
  useEffect(() => {
    if (!trackId1 || !trackId2) {
      setExplanation(null);
      return;
    }

    loadExplanation();
  }, [trackId1, trackId2, topN]);

  const loadExplanation = async () => {
    if (!trackId1 || !trackId2) return;

    setLoading(true);
    setError(null);

    try {
      const result = await similarityService.explainSimilarity(trackId1, trackId2, topN);
      setExplanation(result);
    } catch (err) {
      console.error('Failed to load similarity explanation:', err);
      setError(err instanceof Error ? err.message : 'Failed to load explanation');
      setExplanation(null);
    } finally {
      setLoading(false);
    }
  };

  // Loading state
  if (loading) {
    return <SimilarityLoadingState />;
  }

  // Error state
  if (error) {
    return <SimilarityErrorState error={error} />;
  }

  // Empty state
  if (!trackId1 || !trackId2 || !explanation) {
    return <SimilarityEmptyState />;
  }

  return (
    <Box>
      <SimilarityOverallScore
        score={explanation.similarity_score}
        distance={explanation.distance}
      />

      <SimilarityTopDifferences differences={explanation.top_differences} />

      <SimilarityAllDimensions contributions={explanation.all_contributions} />
    </Box>
  );
};

export default SimilarityVisualization;
