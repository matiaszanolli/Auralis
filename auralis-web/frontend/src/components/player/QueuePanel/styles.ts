import { tokens } from '@/design-system';

export const QUEUE_ITEM_HEIGHT = 60;
export const DRAG_EDGE_ZONE = 60;
export const DRAG_SCROLL_SPEED = 8;

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

  controlBar: {
    display: 'flex',
    gap: tokens.spacing.sm,
    padding: tokens.spacing.md,
    borderBottom: `1px solid ${tokens.colors.border.light}`,
    flexWrap: 'wrap' as const,
  },

  modeButton: {
    padding: `${tokens.spacing.xs} ${tokens.spacing.sm}`,
    borderRadius: tokens.borderRadius.md,
    border: `1px solid ${tokens.colors.border.light}`,
    backgroundColor: tokens.colors.bg.secondary,
    color: tokens.colors.text.primary,
    cursor: 'pointer',
    fontSize: tokens.typography.fontSize.sm,
    fontWeight: tokens.typography.fontWeight.semibold,
    transition: 'all 0.2s',

    ':hover': {
      backgroundColor: tokens.colors.bg.tertiary,
    },

    ':disabled': {
      opacity: 0.5,
      cursor: 'not-allowed',
    },
  },

  modeButtonActive: {
    backgroundColor: tokens.colors.accent.primary,
    color: tokens.colors.text.primaryFull,
    borderColor: tokens.colors.accent.primary,
  },

  repeatModeButtons: {
    display: 'flex',
    gap: tokens.spacing.xs,
    borderLeft: `1px solid ${tokens.colors.border.light}`,
    paddingLeft: tokens.spacing.sm,
    marginLeft: tokens.spacing.sm,
  },

  repeatButton: {
    padding: `${tokens.spacing.xs} ${tokens.spacing.sm}`,
    borderRadius: tokens.borderRadius.md,
    border: `1px solid ${tokens.colors.border.light}`,
    backgroundColor: tokens.colors.bg.secondary,
    color: tokens.colors.text.primary,
    cursor: 'pointer',
    fontSize: tokens.typography.fontSize.sm,
    fontWeight: tokens.typography.fontWeight.bold,
    transition: 'all 0.2s',
    minWidth: '36px',

    ':hover': {
      backgroundColor: tokens.colors.bg.tertiary,
    },

    ':disabled': {
      opacity: 0.5,
      cursor: 'not-allowed',
    },
  },

  repeatButtonActive: {
    backgroundColor: tokens.colors.accent.primary,
    color: tokens.colors.text.primaryFull,
    borderColor: tokens.colors.accent.primary,
  },

  clearButton: {
    marginLeft: 'auto',
    padding: `${tokens.spacing.xs} ${tokens.spacing.sm}`,
    borderRadius: tokens.borderRadius.md,
    border: `1px solid ${tokens.colors.border.light}`,
    backgroundColor: tokens.colors.bg.secondary,
    color: tokens.colors.text.primary,
    cursor: 'pointer',
    fontSize: tokens.typography.fontSize.sm,
    transition: 'all 0.2s',

    ':hover': {
      backgroundColor: tokens.colors.semantic.error,
      color: tokens.colors.text.primaryFull,
    },

    ':disabled': {
      opacity: 0.5,
      cursor: 'not-allowed',
    },
  },

  errorBanner: {
    padding: tokens.spacing.md,
    backgroundColor: tokens.colors.semantic.error,
    color: tokens.colors.text.primaryFull,
    fontSize: tokens.typography.fontSize.sm,
  },

  queueContainer: {
    flex: 1,
    overflow: 'auto',
    display: 'flex',
    flexDirection: 'column' as const,
  },

  queueList: {
    listStyle: 'none',
    margin: 0,
    padding: 0,
  },

  trackItem: {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacing.md,
    padding: tokens.spacing.md,
    borderBottom: `1px solid ${tokens.colors.border.light}`,
    cursor: 'move',
    transition: 'background-color 0.2s, opacity 0.2s',

    ':hover': {
      backgroundColor: tokens.colors.bg.secondary,
    },
  },

  trackItemCurrent: {
    backgroundColor: tokens.colors.bg.secondary,
    borderLeft: `3px solid ${tokens.colors.accent.primary}`,
    paddingLeft: `calc(${tokens.spacing.md} - 3px)`,
  },

  trackItemDragging: {
    opacity: 0.6,
    backgroundColor: tokens.colors.bg.tertiary,
  },

  trackItemHovered: {
    backgroundColor: tokens.colors.bg.secondary,
  },

  trackIndex: {
    width: '32px',
    textAlign: 'center' as const,
    color: tokens.colors.text.tertiary,
    fontWeight: tokens.typography.fontWeight.semibold,
    fontSize: tokens.typography.fontSize.sm,
    flexShrink: 0,
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
    fontSize: tokens.typography.fontSize.md,
    fontWeight: tokens.typography.fontWeight.semibold,
    whiteSpace: 'nowrap' as const,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacing.xs,
  },

  playingIcon: {
    color: tokens.colors.accent.primary,
    fontSize: tokens.typography.fontSize.sm,
    flexShrink: 0,
  },

  trackArtist: {
    color: tokens.colors.text.tertiary,
    fontSize: tokens.typography.fontSize.sm,
    whiteSpace: 'nowrap' as const,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
  },

  trackDuration: {
    color: tokens.colors.text.tertiary,
    fontSize: tokens.typography.fontSize.sm,
    fontVariantNumeric: 'tabular-nums' as const,
    flexShrink: 0,
    minWidth: '48px',
    textAlign: 'right' as const,
  },

  removeButton: {
    padding: tokens.spacing.xs,
    borderRadius: tokens.borderRadius.md,
    border: 'none',
    backgroundColor: tokens.colors.semantic.error,
    color: tokens.colors.text.primaryFull,
    cursor: 'pointer',
    fontSize: tokens.typography.fontSize.md,
    transition: 'opacity 0.2s',
    flexShrink: 0,

    ':hover': {
      opacity: 0.8,
    },

    ':disabled': {
      opacity: 0.5,
      cursor: 'not-allowed',
    },
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
