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
import {
  Box,
  Typography,
  LinearProgress,
  Chip,
  CircularProgress,
  Alert,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Grid,
  Tooltip
} from '@mui/material';
import {
  ExpandMore as ExpandMoreIcon,
  TrendingUp as TrendingUpIcon,
  TrendingDown as TrendingDownIcon
} from '@mui/icons-material';
import similarityService, { SimilarityExplanation } from '../services/similarityService';

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
  topN = 5
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

  const getSimilarityLevel = (score: number): { label: string; color: string } => {
    if (score >= 0.9) return { label: 'Very Similar', color: '#00d4aa' };
    if (score >= 0.8) return { label: 'Similar', color: '#667eea' };
    if (score >= 0.7) return { label: 'Somewhat Similar', color: '#764ba2' };
    if (score >= 0.6) return { label: 'Slightly Similar', color: '#8b92b0' };
    return { label: 'Different', color: '#6c757d' };
  };

  const formatDimensionName = (name: string): string => {
    // Convert snake_case to Title Case
    return name
      .split('_')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  };

  const formatValue = (value: number, dimension: string): string => {
    // Format based on dimension type
    if (dimension.includes('pct')) {
      return `${value.toFixed(1)}%`;
    } else if (dimension.includes('lufs')) {
      return `${value.toFixed(1)} dB`;
    } else if (dimension.includes('crest') || dimension.includes('db')) {
      return `${value.toFixed(1)} dB`;
    } else if (dimension.includes('tempo')) {
      return `${value.toFixed(0)} BPM`;
    } else if (dimension.includes('ratio') || dimension.includes('correlation')) {
      return value.toFixed(2);
    } else {
      return value.toFixed(2);
    }
  };

  // Loading state
  if (loading) {
    return (
      <Box sx={{ p: 2, textAlign: 'center' }}>
        <CircularProgress size={24} sx={{ color: '#667eea' }} />
        <Typography variant="body2" sx={{ mt: 1, color: '#8b92b0' }}>
          Analyzing similarity...
        </Typography>
      </Box>
    );
  }

  // Error state
  if (error) {
    return (
      <Box sx={{ p: 2 }}>
        <Alert severity="error" sx={{ fontSize: '0.875rem' }}>
          {error}
        </Alert>
      </Box>
    );
  }

  // Empty state
  if (!trackId1 || !trackId2 || !explanation) {
    return (
      <Box sx={{ p: 2, textAlign: 'center' }}>
        <Typography variant="body2" sx={{ color: '#8b92b0' }}>
          Select two tracks to compare
        </Typography>
      </Box>
    );
  }

  const { label, color } = getSimilarityLevel(explanation.similarity_score);

  return (
    <Box>
      {/* Overall Similarity Score */}
      <Box sx={{ p: 2, borderBottom: '1px solid rgba(255, 255, 255, 0.1)' }}>
        <Typography variant="subtitle2" sx={{ color: '#ffffff', mb: 1 }}>
          Overall Similarity
        </Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 1 }}>
          <Typography variant="h3" sx={{ color, fontWeight: 700 }}>
            {Math.round(explanation.similarity_score * 100)}%
          </Typography>
          <Chip
            label={label}
            size="small"
            sx={{
              backgroundColor: color,
              color: '#ffffff',
              fontWeight: 600
            }}
          />
        </Box>
        <Typography variant="caption" sx={{ color: '#8b92b0' }}>
          Distance: {explanation.distance.toFixed(4)}
        </Typography>
      </Box>

      {/* Top Differences */}
      <Box sx={{ p: 2, borderBottom: '1px solid rgba(255, 255, 255, 0.1)' }}>
        <Typography variant="subtitle2" sx={{ color: '#ffffff', mb: 1.5 }}>
          Top Differences
        </Typography>
        {explanation.top_differences.map((diff, index) => (
          <Box key={diff.dimension} sx={{ mb: 1.5 }}>
            {/* Dimension Name and Contribution */}
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
              <Typography variant="caption" sx={{ color: '#ffffff', fontWeight: 500 }}>
                {formatDimensionName(diff.dimension)}
              </Typography>
              <Typography variant="caption" sx={{ color: '#8b92b0' }}>
                {(diff.contribution * 100).toFixed(1)}% impact
              </Typography>
            </Box>

            {/* Contribution Bar */}
            <LinearProgress
              variant="determinate"
              value={diff.contribution * 100}
              sx={{
                height: 6,
                borderRadius: 3,
                backgroundColor: 'rgba(255, 255, 255, 0.1)',
                '& .MuiLinearProgress-bar': {
                  backgroundColor: '#667eea',
                  borderRadius: 3
                }
              }}
            />

            {/* Value Comparison */}
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 0.5 }}>
              <Typography variant="caption" sx={{ color: '#8b92b0' }}>
                Track 1: {formatValue(diff.value1, diff.dimension)}
              </Typography>
              <Typography variant="caption" sx={{ color: '#8b92b0' }}>
                Track 2: {formatValue(diff.value2, diff.dimension)}
              </Typography>
            </Box>
          </Box>
        ))}
      </Box>

      {/* All Dimensions (Accordion) */}
      <Accordion
        sx={{
          backgroundColor: 'transparent',
          boxShadow: 'none',
          '&:before': { display: 'none' }
        }}
      >
        <AccordionSummary
          expandIcon={<ExpandMoreIcon sx={{ color: '#8b92b0' }} />}
          sx={{
            px: 2,
            '&:hover': {
              backgroundColor: 'rgba(255, 255, 255, 0.05)'
            }
          }}
        >
          <Typography variant="caption" sx={{ color: '#8b92b0' }}>
            View all {explanation.all_contributions.length} dimensions
          </Typography>
        </AccordionSummary>
        <AccordionDetails sx={{ px: 2, pb: 2 }}>
          <Grid container spacing={1}>
            {explanation.all_contributions
              .sort((a, b) => b.contribution - a.contribution)
              .map((contrib) => (
                <Grid item xs={12} key={contrib.dimension}>
                  <Box sx={{ py: 0.5 }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.25 }}>
                      <Typography variant="caption" sx={{ color: '#ffffff', fontSize: '0.7rem' }}>
                        {formatDimensionName(contrib.dimension)}
                      </Typography>
                      <Typography variant="caption" sx={{ color: '#8b92b0', fontSize: '0.7rem' }}>
                        {(contrib.contribution * 100).toFixed(1)}%
                      </Typography>
                    </Box>
                    <LinearProgress
                      variant="determinate"
                      value={contrib.contribution * 100}
                      sx={{
                        height: 4,
                        borderRadius: 2,
                        backgroundColor: 'rgba(255, 255, 255, 0.08)',
                        '& .MuiLinearProgress-bar': {
                          backgroundColor: '#764ba2',
                          borderRadius: 2
                        }
                      }}
                    />
                  </Box>
                </Grid>
              ))}
          </Grid>
        </AccordionDetails>
      </Accordion>
    </Box>
  );
};

export default SimilarityVisualization;
