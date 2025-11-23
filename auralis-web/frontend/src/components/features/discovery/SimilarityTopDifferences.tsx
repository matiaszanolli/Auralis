import React from 'react';
import { Box, Typography, LinearProgress } from '@mui/material';
import { tokens } from '@/design-system/tokens';
import { colorAuroraPrimary } from './library/Color.styles';
import { SectionDivider, DimensionRow, ValueComparisonBox } from './SimilarityVisualization.styles';
import { useSimilarityFormatting } from './useSimilarityFormatting';

export interface TopDifference {
  dimension: string;
  contribution: number;
  value1: number;
  value2: number;
}

interface SimilarityTopDifferencesProps {
  differences: TopDifference[];
}

/**
 * SimilarityTopDifferences - Displays most impactful dimension differences
 *
 * Shows top N dimensions with contribution bars and value comparisons.
 */
export const SimilarityTopDifferences: React.FC<SimilarityTopDifferencesProps> = ({
  differences,
}) => {
  const { formatDimensionName, formatValue } = useSimilarityFormatting();

  return (
    <SectionDivider>
      <Typography variant="subtitle2" sx={{ color: tokens.colors.text.primary, mb: 1.5 }}>
        Top Differences
      </Typography>
      {differences.map((diff) => (
        <DimensionRow key={diff.dimension}>
          {/* Dimension Name and Contribution */}
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
            <Typography
              variant="caption"
              sx={{ color: tokens.colors.text.primary, fontWeight: 500 }}
            >
              {formatDimensionName(diff.dimension)}
            </Typography>
            <Typography variant="caption" sx={{ color: tokens.colors.text.secondary }}>
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
              backgroundColor: tokens.colors.border.light,
              '& .MuiLinearProgress-bar': {
                backgroundColor: colorAuroraPrimary,
                borderRadius: 3,
              },
            }}
          />

          {/* Value Comparison */}
          <ValueComparisonBox>
            <Typography variant="caption" sx={{ color: tokens.colors.text.secondary }}>
              Track 1: {formatValue(diff.value1, diff.dimension)}
            </Typography>
            <Typography variant="caption" sx={{ color: tokens.colors.text.secondary }}>
              Track 2: {formatValue(diff.value2, diff.dimension)}
            </Typography>
          </ValueComparisonBox>
        </DimensionRow>
      ))}
    </SectionDivider>
  );
};

export default SimilarityTopDifferences;
