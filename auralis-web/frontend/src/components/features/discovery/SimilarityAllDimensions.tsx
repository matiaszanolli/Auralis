import React from 'react';
import {
  Box,
  Grid,
  Typography,
  LinearProgress,
  Accordion,
  AccordionSummary,
  AccordionDetails,
} from '@mui/material';
import { ExpandMore as ExpandMoreIcon } from '@mui/icons-material';
import { tokens } from '@/design-system';
import { useSimilarityFormatting } from './useSimilarityFormatting';

export interface Contribution {
  dimension: string;
  contribution: number;
}

interface SimilarityAllDimensionsProps {
  contributions: Contribution[];
}

/**
 * SimilarityAllDimensions - Expandable section showing all dimension contributions
 *
 * Sorted by contribution percentage in a grid layout.
 */
export const SimilarityAllDimensions: React.FC<SimilarityAllDimensionsProps> = ({
  contributions,
}) => {
  const { formatDimensionName } = useSimilarityFormatting();

  return (
    <Accordion
      sx={{
        backgroundColor: 'transparent',
        boxShadow: 'none',
        '&:before': { display: 'none' },
      }}
    >
      <AccordionSummary
        expandIcon={<ExpandMoreIcon sx={{ color: tokens.colors.text.secondary }} />}
        sx={{
          px: 2,
          '&:hover': {
            backgroundColor: tokens.colors.bg.elevated,
          },
        }}
      >
        <Typography variant="caption" sx={{ color: tokens.colors.text.secondary }}>
          View all {contributions.length} dimensions
        </Typography>
      </AccordionSummary>
      <AccordionDetails sx={{ px: 2, pb: 2 }}>
        <Grid container spacing={1}>
          {contributions
            .sort((a, b) => b.contribution - a.contribution)
            .map((contrib) => (
              <Grid item xs={12} key={contrib.dimension}>
                <Box sx={{ py: 0.5 }}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.25 }}>
                    <Typography
                      variant="caption"
                      sx={{
                        color: tokens.colors.text.primary,
                        fontSize: '0.7rem',
                      }}
                    >
                      {formatDimensionName(contrib.dimension)}
                    </Typography>
                    <Typography
                      variant="caption"
                      sx={{
                        color: tokens.colors.text.secondary,
                        fontSize: '0.7rem',
                      }}
                    >
                      {(contrib.contribution * 100).toFixed(1)}%
                    </Typography>
                  </Box>
                  <LinearProgress
                    variant="determinate"
                    value={contrib.contribution * 100}
                    sx={{
                      height: 4,
                      borderRadius: 2,
                      backgroundColor: tokens.colors.border.light,
                      '& .MuiLinearProgress-bar': {
                        backgroundColor: tokens.colors.accent.secondary,
                        borderRadius: 2,
                      },
                    }}
                  />
                </Box>
              </Grid>
            ))}
        </Grid>
      </AccordionDetails>
    </Accordion>
  );
};

export default SimilarityAllDimensions;
