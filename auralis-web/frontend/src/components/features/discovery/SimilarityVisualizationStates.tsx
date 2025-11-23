import React from 'react';
import { Box, CircularProgress, Typography, Alert } from '@mui/material';
import { tokens } from '@/design-system/tokens';
import { colorAuroraPrimary } from '../../library/Styles/Color.styles';

interface SimilarityLoadingStateProps {
  message?: string;
}

export const SimilarityLoadingState: React.FC<SimilarityLoadingStateProps> = ({
  message = 'Analyzing similarity...',
}) => (
  <Box sx={{ p: 2, textAlign: 'center' }}>
    <CircularProgress size={24} sx={{ color: colorAuroraPrimary }} />
    <Typography variant="body2" sx={{ mt: 1, color: tokens.colors.text.secondary }}>
      {message}
    </Typography>
  </Box>
);

interface SimilarityErrorStateProps {
  error: string;
}

export const SimilarityErrorState: React.FC<SimilarityErrorStateProps> = ({ error }) => (
  <Box sx={{ p: 2 }}>
    <Alert severity="error" sx={{ fontSize: '0.875rem' }}>
      {error}
    </Alert>
  </Box>
);

export const SimilarityEmptyState: React.FC = () => (
  <Box sx={{ p: 2, textAlign: 'center' }}>
    <Typography variant="body2" sx={{ color: tokens.colors.text.secondary }}>
      Select two tracks to compare
    </Typography>
  </Box>
);

export default {
  SimilarityLoadingState,
  SimilarityErrorState,
  SimilarityEmptyState,
};
