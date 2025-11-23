import React from 'react';
import {
  Container,
  Skeleton,
  Box
} from '@mui/material';

/**
 * DetailLoading - Loading skeleton for detail view
 *
 * Displays:
 * - Header skeleton (artist image, title, metadata)
 * - Content skeleton (tabs and content area)
 */
export const DetailLoading: React.FC = () => {
  return (
    <Container maxWidth="xl" sx={{ py: 4 }}>
      <Skeleton
        variant="rectangular"
        height={300}
        sx={{ borderRadius: 2, mb: 4 }}
      />
      <Skeleton
        variant="rectangular"
        height={400}
        sx={{ borderRadius: 2 }}
      />
    </Container>
  );
};

export default DetailLoading;
