import { tokens } from '@/design-system';

export const resultItemStyles = {
  resultItem: {
    borderBottom: `1px solid ${tokens.colors.border.light}`,
    transition: 'background-color 0.2s',

    ':hover': {
      backgroundColor: tokens.colors.bg.secondary,
    },
  },

  resultItemHovered: {
    backgroundColor: tokens.colors.bg.secondary,
  },

  resultItemContent: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: tokens.spacing.md,
    padding: tokens.spacing.md,
  },

  resultInfo: {
    flex: 1,
    minWidth: 0,
    cursor: 'pointer',
    display: 'flex',
    flexDirection: 'column' as const,
    gap: tokens.spacing.xs,
  },

  resultTitle: {
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

  resultSubtitle: {
    color: tokens.colors.text.tertiary,
    fontSize: tokens.typography.fontSize.sm,
    whiteSpace: 'nowrap' as const,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacing.xs,
  },

  resultAlbum: {
    color: tokens.colors.text.tertiary,
    fontSize: tokens.typography.fontSize.xs,
    whiteSpace: 'nowrap' as const,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacing.xs,
  },

  matchBadge: {
    display: 'inline-block',
    backgroundColor: tokens.colors.accent.primary,
    color: tokens.colors.text.primaryFull,
    padding: `2px 6px`,
    borderRadius: tokens.borderRadius.sm,
    fontSize: '10px',
    fontWeight: tokens.typography.fontWeight.bold,
    whiteSpace: 'nowrap' as const,
    flexShrink: 0,
  },

  resultActions: {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacing.sm,
    flexShrink: 0,
  },

  resultDuration: {
    color: tokens.colors.text.tertiary,
    fontSize: tokens.typography.fontSize.sm,
    fontVariantNumeric: 'tabular-nums' as const,
    minWidth: '48px',
    textAlign: 'right' as const,
  },

  resultRemoveButton: {
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
  },
};
