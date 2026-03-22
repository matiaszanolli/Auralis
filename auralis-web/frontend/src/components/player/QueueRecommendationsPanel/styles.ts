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
    transition: 'background-color 0.2s',

    ':hover': {
      backgroundColor: tokens.colors.bg.secondary,
    },
  },

  tabBar: {
    display: 'flex',
    gap: tokens.spacing.xs,
    padding: tokens.spacing.sm,
    borderBottom: `1px solid ${tokens.colors.border.light}`,
    overflow: 'auto',
  },

  tab: {
    padding: `${tokens.spacing.xs} ${tokens.spacing.sm}`,
    borderRadius: tokens.borderRadius.sm,
    border: `1px solid ${tokens.colors.border.light}`,
    backgroundColor: tokens.colors.bg.secondary,
    color: tokens.colors.text.primary,
    cursor: 'pointer',
    fontSize: tokens.typography.fontSize.sm,
    fontWeight: tokens.typography.fontWeight.semibold,
    transition: 'all 0.2s',
    whiteSpace: 'nowrap' as const,

    ':hover': {
      backgroundColor: tokens.colors.bg.tertiary,
    },
  },

  tabActive: {
    backgroundColor: tokens.colors.accent.primary,
    color: tokens.colors.text.primaryFull,
    borderColor: tokens.colors.accent.primary,
  },

  content: {
    flex: 1,
    overflow: 'auto',
  },

  tabContent: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: tokens.spacing.xs,
    padding: tokens.spacing.md,
  },

  recommendationItem: {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacing.md,
    padding: tokens.spacing.sm,
    backgroundColor: tokens.colors.bg.secondary,
    borderRadius: tokens.borderRadius.sm,
    transition: 'background-color 0.2s',
    cursor: 'pointer',
  },

  recommendationItemHovered: {
    backgroundColor: tokens.colors.bg.tertiary,
  },

  recInfo: {
    flex: 1,
    minWidth: 0,
    display: 'flex',
    flexDirection: 'column' as const,
    gap: tokens.spacing.xs,
  },

  recTitle: {
    color: tokens.colors.text.primary,
    fontSize: tokens.typography.fontSize.sm,
    fontWeight: tokens.typography.fontWeight.semibold,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap' as const,
  },

  recArtist: {
    color: tokens.colors.text.tertiary,
    fontSize: tokens.typography.fontSize.xs,
  },

  recReason: {
    color: tokens.colors.accent.primary,
    fontSize: tokens.typography.fontSize.xs,
    fontStyle: 'italic',
  },

  recScore: {
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'center',
    minWidth: '40px',
  },

  scoreValue: {
    fontSize: tokens.typography.fontSize.sm,
    fontWeight: tokens.typography.fontWeight.bold,
    color: tokens.colors.accent.primary,
  },

  trackItem: {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacing.md,
    padding: tokens.spacing.sm,
    backgroundColor: tokens.colors.bg.secondary,
    borderRadius: tokens.borderRadius.sm,
    transition: 'background-color 0.2s',
    cursor: 'pointer',
  },

  trackItemHovered: {
    backgroundColor: tokens.colors.bg.tertiary,
  },

  trackIndex: {
    color: tokens.colors.text.tertiary,
    fontSize: tokens.typography.fontSize.sm,
    fontWeight: tokens.typography.fontWeight.bold,
    minWidth: '24px',
    textAlign: 'center' as const,
  },

  trackInfo: {
    flex: 1,
    minWidth: 0,
    display: 'flex',
    flexDirection: 'column' as const,
    gap: tokens.spacing.xs,
  },

  trackTitle: {
    color: tokens.colors.text.primary,
    fontSize: tokens.typography.fontSize.sm,
    fontWeight: tokens.typography.fontWeight.semibold,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap' as const,
  },

  trackArtist: {
    color: tokens.colors.text.tertiary,
    fontSize: tokens.typography.fontSize.xs,
  },

  artistCard: {
    padding: tokens.spacing.md,
    backgroundColor: tokens.colors.bg.secondary,
    borderRadius: tokens.borderRadius.sm,
    border: `1px solid ${tokens.colors.border.light}`,
    transition: 'all 0.2s',
  },

  artistCardHovered: {
    backgroundColor: tokens.colors.bg.tertiary,
    borderColor: tokens.colors.accent.primary,
  },

  artistName: {
    color: tokens.colors.text.primary,
    fontSize: tokens.typography.fontSize.md,
    fontWeight: tokens.typography.fontWeight.bold,
    marginBottom: tokens.spacing.xs,
  },

  artistCount: {
    color: tokens.colors.text.tertiary,
    fontSize: tokens.typography.fontSize.xs,
    marginBottom: tokens.spacing.sm,
  },

  artistTracks: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: tokens.spacing.xs,
  },

  artistTrackItem: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    fontSize: tokens.typography.fontSize.xs,
    color: tokens.colors.text.secondary,
    opacity: 0.7,
  },

  artistTrackItemVisible: {
    opacity: 1,
  },

  artistTrackTitle: {
    flex: 1,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap' as const,
  },

  addButton: {
    padding: tokens.spacing.xs,
    borderRadius: tokens.borderRadius.sm,
    border: 'none',
    backgroundColor: tokens.colors.accent.primary,
    color: tokens.colors.text.primaryFull,
    cursor: 'pointer',
    fontSize: tokens.typography.fontSize.md,
    fontWeight: tokens.typography.fontWeight.bold,
    transition: 'opacity 0.2s',
    flexShrink: 0,
    minWidth: '28px',
    height: '28px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',

    ':hover': {
      opacity: 0.8,
    },
  },

  addButtonSmall: {
    padding: '2px 4px',
    borderRadius: tokens.borderRadius.sm,
    border: 'none',
    backgroundColor: tokens.colors.accent.primary,
    color: tokens.colors.text.primaryFull,
    cursor: 'pointer',
    fontSize: tokens.typography.fontSize.xs,
    fontWeight: tokens.typography.fontWeight.bold,
    transition: 'opacity 0.2s',
  },

  emptyState: {
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'center',
    justifyContent: 'center',
    flex: 1,
    color: tokens.colors.text.tertiary,
    textAlign: 'center' as const,
    padding: tokens.spacing.xl,
  },

  emptySubtext: {
    fontSize: tokens.typography.fontSize.sm,
    color: tokens.colors.text.tertiary,
    marginTop: tokens.spacing.sm,
  },
};
