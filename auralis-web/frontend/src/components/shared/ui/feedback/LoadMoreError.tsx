/**
 * LoadMoreError - inline "couldn't load the next page" row with a Retry.
 *
 * A failed page 2+ used to replace the whole loaded list with an error
 * EmptyState (no retry), throwing away the user's rows and scroll position on
 * one transient 503 — e.g. a SQLite lock during a scan (#5870). The rows stay;
 * this row sits where the next page would appear.
 */

import { Box, Typography } from '@mui/material';
import { Button } from '@/design-system/primitives/Button';
import { tokens } from '@/design-system';

interface LoadMoreErrorProps {
  /** What failed to load, e.g. "albums". */
  noun: string;
  onRetry: () => void;
}

export const LoadMoreError = ({ noun, onRetry }: LoadMoreErrorProps) => (
  <Box
    role="alert"
    sx={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      gap: tokens.spacing.cluster,
      padding: tokens.spacing.group,
    }}
  >
    <Typography variant="body2" sx={{ color: 'text.secondary' }}>
      Couldn&apos;t load more {noun}.
    </Typography>
    <Button variant="ghost" size="sm" onClick={onRetry}>
      Retry
    </Button>
  </Box>
);

export default LoadMoreError;
