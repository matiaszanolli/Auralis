import React from 'react';
import { Person } from '@mui/material';
import { EmptyState } from '../../shared/ui/feedback';

interface ArtistListEmptyStateProps {
  loading: boolean;
  error: string | null;
}

/**
 * ArtistListEmptyState - Displays loading, error, or empty state
 *
 * Shows appropriate empty state message based on loading/error conditions.
 * Returns null if data is loaded and available.
 *
 * @example
 * <ArtistListEmptyState loading={loading} error={error} />
 */
export const ArtistListEmptyState: React.FC<ArtistListEmptyStateProps> = ({
  loading,
  error,
}) => {
  if (loading) {
    return null; // Show loading skeleton in parent
  }

  if (error) {
    return (
      <EmptyState
        title="Error Loading Artists"
        description={error}
      />
    );
  }

  return (
    <EmptyState
      title="No Artists Yet"
      description="Your artist library will appear here once you scan your music folder"
      customIcon={<Person sx={{ fontSize: 64, opacity: 0.3 }} />}
    />
  );
};

export default ArtistListEmptyState;
