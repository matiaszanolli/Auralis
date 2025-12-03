import React from 'react';
import { Box, Typography } from '@mui/material';
import { tokens, Chip } from '@/design-system';
import { SectionDivider } from './SimilarityVisualization.styles';
import { useSimilarityFormatting } from './useSimilarityFormatting';

interface SimilarityOverallScoreProps {
  score: number;
  distance: number;
}

/**
 * SimilarityOverallScore - Displays overall similarity percentage and label
 *
 * Shows score as percentage, label (Very Similar/Similar/etc.), and distance metric.
 */
export const SimilarityOverallScore: React.FC<SimilarityOverallScoreProps> = ({
  score,
  distance,
}) => {
  const { getSimilarityLevel } = useSimilarityFormatting();
  const { label, color } = getSimilarityLevel(score);

  return (
    <SectionDivider>
      <Typography variant="subtitle2" sx={{ color: tokens.colors.text.primary, mb: 1 }}>
        Overall Similarity
      </Typography>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 1 }}>
        <Typography variant="h3" sx={{ color, fontWeight: 700 }}>
          {Math.round(score * 100)}%
        </Typography>
        <Chip
          label={label}
          size="small"
          sx={{
            backgroundColor: color,
            color: tokens.colors.text.primary,
            fontWeight: 600,
          }}
        />
      </Box>
      <Typography variant="caption" sx={{ color: tokens.colors.text.secondary }}>
        Distance: {distance.toFixed(4)}
      </Typography>
    </SectionDivider>
  );
};

export default SimilarityOverallScore;
