import { tokens } from '@/design-system';

export { resultItemStyles } from './resultItemStyles';

export const panelStyles = {
  overlay: {
    position: 'fixed' as const,
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: tokens.colors.opacityScale.dark.intense,
    display: 'flex',
    alignItems: 'flex-start',
    justifyContent: 'center',
    paddingTop: tokens.spacing.xl,
    zIndex: 1000,
  },

  panel: {
    backgroundColor: tokens.colors.bg.primary,
    borderRadius: tokens.borderRadius.lg,
    border: `1px solid ${tokens.colors.border.light}`,
    display: 'flex',
    flexDirection: 'column' as const,
    width: '90%',
    maxWidth: '600px',
    maxHeight: '80vh',
    boxShadow: `0 10px 40px ${tokens.colors.opacityScale.dark.strong}`,
  },

  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: tokens.spacing.lg,
    borderBottom: `1px solid ${tokens.colors.border.light}`,
    flexShrink: 0,
  },

  title: {
    margin: 0,
    fontSize: tokens.typography.fontSize.xl,
    fontWeight: tokens.typography.fontWeight.bold,
    color: tokens.colors.text.primary,
  },

  closeButton: {
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

  searchSection: {
    padding: tokens.spacing.lg,
    borderBottom: `1px solid ${tokens.colors.border.light}`,
    flexShrink: 0,
    display: 'flex',
    flexDirection: 'column' as const,
    gap: tokens.spacing.md,
  },

  searchInputWrapper: {
    position: 'relative' as const,
    display: 'flex',
    alignItems: 'center',
  },

  searchInput: {
    width: '100%',
    padding: `${tokens.spacing.sm} ${tokens.spacing.md}`,
    borderRadius: tokens.borderRadius.md,
    border: `1px solid ${tokens.colors.border.light}`,
    backgroundColor: tokens.colors.bg.secondary,
    color: tokens.colors.text.primary,
    fontSize: tokens.typography.fontSize.md,
    fontFamily: 'inherit',
    transition: 'border-color 0.2s',

    ':focus': {
      outline: 'none',
      borderColor: tokens.colors.accent.primary,
    },

    '::placeholder': {
      color: tokens.colors.text.tertiary,
    },
  },

  clearSearchButton: {
    position: 'absolute' as const,
    right: tokens.spacing.sm,
    background: 'none',
    border: 'none',
    color: tokens.colors.text.tertiary,
    cursor: 'pointer',
    fontSize: tokens.typography.fontSize.md,
    padding: tokens.spacing.xs,
    borderRadius: tokens.borderRadius.sm,
    transition: 'color 0.2s',

    ':hover': {
      color: tokens.colors.text.primary,
    },
  },

  filterButtons: {
    display: 'flex',
    gap: tokens.spacing.sm,
    flexWrap: 'wrap' as const,
  },

  filterButton: {
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
  },

  filterButtonActive: {
    backgroundColor: tokens.colors.accent.primary,
    color: tokens.colors.text.primaryFull,
    borderColor: tokens.colors.accent.primary,
  },

  resultsInfo: {
    fontSize: tokens.typography.fontSize.sm,
    color: tokens.colors.text.tertiary,
    padding: `${tokens.spacing.xs} ${tokens.spacing.sm}`,
  },

  resultsContainer: {
    flex: 1,
    overflow: 'auto',
    display: 'flex',
    flexDirection: 'column' as const,
  },

  resultsList: {
    listStyle: 'none',
    margin: 0,
    padding: 0,
  },

  noResults: {
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'center',
    justifyContent: 'center',
    flex: 1,
    color: tokens.colors.text.tertiary,
    textAlign: 'center' as const,
    padding: tokens.spacing.xl,
  },

  noResultsHint: {
    fontSize: tokens.typography.fontSize.sm,
    color: tokens.colors.text.tertiary,
    marginTop: tokens.spacing.sm,
  },

  footer: {
    padding: tokens.spacing.lg,
    borderTop: `1px solid ${tokens.colors.border.light}`,
    display: 'flex',
    justifyContent: 'flex-end',
    flexShrink: 0,
  },

  clearAllButton: {
    padding: `${tokens.spacing.xs} ${tokens.spacing.md}`,
    borderRadius: tokens.borderRadius.md,
    border: `1px solid ${tokens.colors.border.light}`,
    backgroundColor: tokens.colors.bg.secondary,
    color: tokens.colors.text.primary,
    cursor: 'pointer',
    fontSize: tokens.typography.fontSize.sm,
    fontWeight: tokens.typography.fontWeight.semibold,
    transition: 'all 0.2s',

    ':hover': {
      backgroundColor: tokens.colors.semantic.error,
      color: tokens.colors.text.primaryFull,
    },
  },
};
