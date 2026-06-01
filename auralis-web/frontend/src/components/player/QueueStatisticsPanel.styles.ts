/**
 * QueueStatisticsPanel styles
 *
 * Extracted from QueueStatisticsPanel.tsx (#3938 / CQ-2) to keep the component
 * under the project's 300-line module limit. Values unchanged.
 */

import { tokens } from '@/design-system';

export const styles = {
  container: {
    display: 'flex',
    flexDirection: 'column' as const,
    width: '100%',
    height: '100%',
    backgroundColor: tokens.colors.bg.primary,
    borderLeft: `1px solid ${tokens.colors.border.light}`,
    overflow: 'hidden',
  },

  collapsedContainer: {
    display: 'flex',
    padding: tokens.spacing.md,
  },

  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: tokens.spacing.md,
    borderBottom: `1px solid ${tokens.colors.border.light}`,
  },

  title: {
    margin: 0,
    fontSize: tokens.typography.fontSize.lg,
    fontWeight: tokens.typography.fontWeight.bold,
    color: tokens.colors.text.primary,
  },

  toggleButton: {
    background: 'none',
    border: 'none',
    color: tokens.colors.text.primary,
    cursor: 'pointer',
    fontSize: tokens.typography.fontSize.lg,
    padding: tokens.spacing.sm,
    borderRadius: tokens.borderRadius.md,
    transition: tokens.transitions.background,

    ':hover': {
      backgroundColor: tokens.colors.bg.secondary,
    },
  },

  content: {
    flex: 1,
    overflow: 'auto',
    padding: tokens.spacing.md,
    display: 'flex',
    flexDirection: 'column' as const,
    gap: tokens.spacing.lg,
  },

  section: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: tokens.spacing.sm,
  },

  sectionTitle: {
    margin: 0,
    fontSize: tokens.typography.fontSize.md,
    fontWeight: tokens.typography.fontWeight.bold,
    color: tokens.colors.text.primary,
    paddingBottom: tokens.spacing.xs,
    borderBottom: `1px solid ${tokens.colors.border.light}`,
  },

  summaryGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(2, 1fr)',
    gap: tokens.spacing.md,
  },

  statItem: {
    padding: tokens.spacing.sm,
    backgroundColor: tokens.colors.bg.secondary,
    borderRadius: tokens.borderRadius.md,
    border: `1px solid ${tokens.colors.border.light}`,
    display: 'flex',
    flexDirection: 'column' as const,
    gap: tokens.spacing.xs,
  },

  statLabel: {
    fontSize: tokens.typography.fontSize.sm,
    color: tokens.colors.text.tertiary,
    fontWeight: tokens.typography.fontWeight.semibold,
  },

  statValue: {
    fontSize: tokens.typography.fontSize.lg,
    fontWeight: tokens.typography.fontWeight.bold,
    color: tokens.colors.text.primary,
  },

  statsGrid: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: tokens.spacing.xs,
  },

  statRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: tokens.spacing.sm,
    backgroundColor: tokens.colors.bg.secondary,
    borderRadius: tokens.borderRadius.sm,
    fontSize: tokens.typography.fontSize.sm,
  },

  statRowLabel: {
    color: tokens.colors.text.tertiary,
    fontWeight: tokens.typography.fontWeight.semibold,
  },

  statRowValue: {
    color: tokens.colors.text.primary,
    fontWeight: tokens.typography.fontWeight.bold,
    fontVariantNumeric: 'tabular-nums' as const,
  },

  listSection: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: tokens.spacing.xs,
  },

  topItemRow: {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacing.sm,
    padding: tokens.spacing.sm,
    backgroundColor: tokens.colors.bg.secondary,
    borderRadius: tokens.borderRadius.sm,
    fontSize: tokens.typography.fontSize.sm,
  },

  topItemRank: {
    color: tokens.colors.accent.primary,
    fontWeight: tokens.typography.fontWeight.bold,
    minWidth: '30px',
  },

  topItemValue: {
    flex: 1,
    color: tokens.colors.text.primary,
    fontWeight: tokens.typography.fontWeight.semibold,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap' as const,
  },

  topItemStats: {
    color: tokens.colors.text.tertiary,
    fontSize: tokens.typography.fontSize.xs,
    flexShrink: 0,
  },

  qualityContainer: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: tokens.spacing.sm,
  },

  qualityBadge: {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacing.sm,
    padding: `${tokens.spacing.sm} ${tokens.spacing.md}`,
    borderRadius: tokens.borderRadius.md,
    color: tokens.colors.text.primaryFull, // White text on colored badge
    fontWeight: tokens.typography.fontWeight.bold,
    fontSize: tokens.typography.fontSize.sm,
  },

  qualityIcon: {
    fontSize: tokens.typography.fontSize.lg,
  },

  qualityText: {
    flex: 1,
  },

  issuesList: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: tokens.spacing.xs,
  },

  issueItem: {
    fontSize: tokens.typography.fontSize.sm,
    color: tokens.colors.text.tertiary,
    padding: tokens.spacing.xs,
    paddingLeft: tokens.spacing.sm,
  },

  emptyState: {
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'center',
    justifyContent: 'center',
    flex: 1,
    color: tokens.colors.text.tertiary,
    textAlign: 'center' as const,
  },

  emptySubtext: {
    fontSize: tokens.typography.fontSize.sm,
    color: tokens.colors.text.tertiary,
    marginTop: tokens.spacing.sm,
  },
};
