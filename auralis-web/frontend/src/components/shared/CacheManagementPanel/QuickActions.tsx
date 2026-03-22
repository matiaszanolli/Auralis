import Box from '@mui/material/Box';
import { tokens } from '@/design-system';

interface QuickActionsProps {
  onClearClick: () => void;
  onRefreshClick: () => void;
  clearDisabled: boolean;
  refreshDisabled: boolean;
  clearLoading: boolean;
  statsLoading: boolean;
}

export function QuickActions({
  onClearClick,
  onRefreshClick,
  clearDisabled,
  refreshDisabled,
  clearLoading,
  statsLoading,
}: QuickActionsProps) {
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
        gap: tokens.spacing.md,
      }}
    >
      <Box
        component="button"
        onClick={onClearClick}
        disabled={clearDisabled}
        sx={{
          padding: tokens.spacing.md,
          background: tokens.colors.semantic.error,
          border: 'none',
          borderRadius: '8px',
          color: tokens.colors.text.primary,
          fontSize: tokens.typography.fontSize.sm,
          fontWeight: tokens.typography.fontWeight.semibold,
          cursor: clearLoading ? 'not-allowed' : 'pointer',
          opacity: clearLoading ? 0.6 : 0.9,
          transition: 'all 0.2s',
          '&:hover:not(:disabled)': {
            opacity: 1,
          },
        }}
      >
        {clearLoading ? 'Clearing...' : '🗑️ Clear All Cache'}
      </Box>

      <Box
        component="button"
        onClick={onRefreshClick}
        disabled={refreshDisabled}
        sx={{
          padding: tokens.spacing.md,
          background: tokens.colors.bg.tertiary,
          border: `1px solid ${tokens.colors.border.medium}`,
          borderRadius: '8px',
          color: tokens.colors.text.primary,
          fontSize: tokens.typography.fontSize.sm,
          fontWeight: tokens.typography.fontWeight.semibold,
          cursor: statsLoading ? 'not-allowed' : 'pointer',
          opacity: statsLoading ? 0.6 : 0.9,
          transition: 'all 0.2s',
          '&:hover:not(:disabled)': {
            opacity: 1,
          },
        }}
      >
        {statsLoading ? 'Refreshing...' : '🔄 Refresh Stats'}
      </Box>
    </div>
  );
}
