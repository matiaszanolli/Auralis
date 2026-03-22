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
      <button
        onClick={onClearClick}
        disabled={clearDisabled}
        style={{
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
        }}
        onMouseOver={(e) => {
          if (!clearLoading) {
            e.currentTarget.style.opacity = '1';
          }
        }}
        onMouseOut={(e) => {
          if (!clearLoading) {
            e.currentTarget.style.opacity = '0.9';
          }
        }}
      >
        {clearLoading ? 'Clearing...' : '🗑️ Clear All Cache'}
      </button>

      <button
        onClick={onRefreshClick}
        disabled={refreshDisabled}
        style={{
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
        }}
        onMouseOver={(e) => {
          if (!statsLoading) {
            e.currentTarget.style.opacity = '1';
          }
        }}
        onMouseOut={(e) => {
          if (!statsLoading) {
            e.currentTarget.style.opacity = '0.9';
          }
        }}
      >
        {statsLoading ? 'Refreshing...' : '🔄 Refresh Stats'}
      </button>
    </div>
  );
}
