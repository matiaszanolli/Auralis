
import { ExpandMore as ExpandMoreIcon } from '@mui/icons-material';
import { tokens } from '@/design-system';
import { useSimilarityFormatting } from './useSimilarityFormatting';
import { LinearProgress } from '@/design-system';
import { Box, Typography, Accordion, AccordionSummary, AccordionDetails,  } from '@mui/material';
import Grid2 from '@mui/material/Grid';

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
export const SimilarityAllDimensions = ({
  contributions,
}: SimilarityAllDimensionsProps) => {
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
        <Grid2 container spacing={1}>
          {contributions
            .sort((a, b) => b.contribution - a.contribution)
            .map((contrib) => (
              <Grid2 key={contrib.dimension} size={12}>
                <Box sx={{ py: 0.5 }}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.25 }}>
                    <Typography
                      variant="caption"
                      sx={{
                        color: tokens.colors.text.primary,
                        fontSize: tokens.typography.fontSize.xs,
                      }}
                    >
                      {formatDimensionName(contrib.dimension)}
                    </Typography>
                    <Typography
                      variant="caption"
                      sx={{
                        color: tokens.colors.text.secondary,
                        fontSize: tokens.typography.fontSize.xs,
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
              </Grid2>
            ))}
        </Grid2>
      </AccordionDetails>
    </Accordion>
  );
};

export default SimilarityAllDimensions;
