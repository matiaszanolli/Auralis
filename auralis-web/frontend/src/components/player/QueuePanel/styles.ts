import { tokens } from '@/design-system';
import { themeVars } from '@/theme/semanticTheme';
import { progressBarStyles } from '@/components/player/ProgressBar.styles';

export const QUEUE_ITEM_HEIGHT = 60;
export const DRAG_EDGE_ZONE = 60;
export const DRAG_SCROLL_SPEED = 8;

export const styles = {
  container: {
    display: 'flex',
    flexDirection: 'column' as const,
    width: '100%',
    height: '100%',
    backgroundColor: themeVars.surfacePrimary,
    borderLeft: `1px solid ${themeVars.borderSubtle}`,
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
    borderBottom: `1px solid ${themeVars.borderSubtle}`,
  },

  title: {
    margin: 0,
    fontSize: tokens.typography.fontSize.lg,
    fontWeight: tokens.typography.fontWeight.bold,
    color: themeVars.textPrimary,
  },

  toggleButton: {
    background: 'none',
    border: 'none',
    color: themeVars.textPrimary,
    cursor: 'pointer',
    fontSize: tokens.typography.fontSize.lg,
    padding: tokens.spacing.sm,
    borderRadius: tokens.borderRadius.md,
    transition: tokens.transitions.background,

    ':hover': {
      backgroundColor: themeVars.accentSoft,
    },
  },

  controlBar: {
    display: 'flex',
    gap: tokens.spacing.sm,
    padding: tokens.spacing.md,
    borderBottom: `1px solid ${themeVars.borderSubtle}`,
    flexWrap: 'wrap' as const,
  },

  modeButton: {
    padding: `${tokens.spacing.xs} ${tokens.spacing.sm}`,
    borderRadius: tokens.borderRadius.md,
    border: `1px solid ${themeVars.borderDefault}`,
    backgroundColor: themeVars.surfaceSecondary,
    color: themeVars.textPrimary,
    cursor: 'pointer',
    fontSize: tokens.typography.fontSize.sm,
    fontWeight: tokens.typography.fontWeight.semibold,
    transition: tokens.transitions.hover_out,

    ':hover': {
      backgroundColor: themeVars.accentSoft,
    },

    ':disabled': {
      opacity: 0.5,
      cursor: 'not-allowed',
    },
  },

  modeButtonActive: {
    backgroundColor: themeVars.accent,
    color: themeVars.textStrong,
    borderColor: themeVars.accent,
  },

  repeatModeButtons: {
    display: 'flex',
    gap: tokens.spacing.xs,
    borderLeft: `1px solid ${themeVars.borderSubtle}`,
    paddingLeft: tokens.spacing.sm,
    marginLeft: tokens.spacing.sm,
  },

  repeatButton: {
    padding: `${tokens.spacing.xs} ${tokens.spacing.sm}`,
    borderRadius: tokens.borderRadius.md,
    border: `1px solid ${themeVars.borderDefault}`,
    backgroundColor: themeVars.surfaceSecondary,
    color: themeVars.textPrimary,
    cursor: 'pointer',
    fontSize: tokens.typography.fontSize.sm,
    fontWeight: tokens.typography.fontWeight.bold,
    transition: tokens.transitions.hover_out,
    minWidth: '36px',

    ':hover': {
      backgroundColor: themeVars.accentSoft,
    },

    ':disabled': {
      opacity: 0.5,
      cursor: 'not-allowed',
    },
  },

  repeatButtonActive: {
    backgroundColor: themeVars.accent,
    color: themeVars.textStrong,
    borderColor: themeVars.accent,
  },

  clearButton: {
    marginLeft: 'auto',
    padding: `${tokens.spacing.xs} ${tokens.spacing.sm}`,
    borderRadius: tokens.borderRadius.md,
    border: `1px solid ${themeVars.borderDefault}`,
    backgroundColor: themeVars.surfaceSecondary,
    color: themeVars.textPrimary,
    cursor: 'pointer',
    fontSize: tokens.typography.fontSize.sm,
    transition: tokens.transitions.hover_out,

    ':hover': {
      backgroundColor: themeVars.error,
      color: themeVars.textStrong,
    },

    ':disabled': {
      opacity: 0.5,
      cursor: 'not-allowed',
    },
  },

  errorBanner: {
    padding: tokens.spacing.md,
    backgroundColor: themeVars.error,
    color: themeVars.textStrong,
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
    borderBottom: `1px solid ${themeVars.borderSubtle}`,
    cursor: 'move',
    transition: `${tokens.transitions.background}, ${tokens.transitions.opacity}`,

    ':hover': {
      backgroundColor: themeVars.accentSoft,
    },
  },

  trackItemCurrent: {
    backgroundColor: themeVars.accentSoft,
    borderLeft: `3px solid ${themeVars.accent}`,
    paddingLeft: `calc(${tokens.spacing.md} - 3px)`,
  },

  trackItemDragging: {
    opacity: 0.6,
    backgroundColor: themeVars.surfaceRaised,
  },

  trackItemHovered: {
    backgroundColor: themeVars.accentSoft,
  },

  trackIndex: {
    width: '32px',
    textAlign: 'center' as const,
    color: themeVars.textMuted,
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
    color: themeVars.textPrimary,
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
    color: themeVars.accent,
    fontSize: tokens.typography.fontSize.sm,
    flexShrink: 0,
  },

  trackArtist: {
    color: themeVars.textMuted,
    fontSize: tokens.typography.fontSize.sm,
    whiteSpace: 'nowrap' as const,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
  },

  trackDuration: {
    color: themeVars.textMuted,
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
    backgroundColor: themeVars.error,
    color: themeVars.textStrong,
    cursor: 'pointer',
    fontSize: tokens.typography.fontSize.md,
    transition: tokens.transitions.opacity,
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
    color: themeVars.textMuted,
    textAlign: 'center' as const,
  },

  emptySubtext: {
    fontSize: tokens.typography.fontSize.sm,
    color: themeVars.textMuted,
    marginTop: tokens.spacing.sm,
  },

  /**
   * Screen-reader-only, for the reorder live region (#4536). Reuses the single
   * definition in ProgressBar.styles rather than restating the clip-path recipe
   * — the #3651 `clip` -> `clip-path` fix had to be applied there once already,
   * and a second copy is a second thing to miss next time.
   */
  visuallyHidden: progressBarStyles.srOnly,
};
