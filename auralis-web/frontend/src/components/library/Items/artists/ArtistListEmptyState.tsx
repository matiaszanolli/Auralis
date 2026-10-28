
import Person from '@mui/icons-material/Person';
import { EmptyState } from '@/components/shared/ui/feedback';

interface ArtistListEmptyStateProps {
  loading: boolean;
  error: string | null;
  onRetry?: () => void;
}

/**
 * ArtistListEmptyState - Displays loading, error, or empty state
 *
 * Shows appropriate empty state message based on loading/error conditions.
 * Returns null if data is loaded and available.
 *
 * @example
 * <ArtistListEmptyState loading={loading} error={error} onRetry={refetch} />
 */
export const ArtistListEmptyState = ({
  loading,
  error,
  onRetry,
}: ArtistListEmptyStateProps) => {
  if (loading) {
    return null; // Show loading skeleton in parent
  }

  if (error) {
    return (
      <EmptyState
        role="alert"
        title="Error Loading Artists"
        description={error}
        actionLabel={onRetry ? 'Retry' : undefined}
        onAction={onRetry}
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
