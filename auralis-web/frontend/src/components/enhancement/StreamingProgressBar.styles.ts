/**
 * Styles for StreamingProgressBar
 *
 * Extracted from StreamingProgressBar.tsx (#3939 / CQ-3) so the component body
 * stays focused on structure. All values derive from design-system tokens.
 */

import { CSSProperties } from 'react';
import { tokens } from '@/design-system';

export const styles: Record<string, CSSProperties> = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacing.md,
    padding: tokens.spacing.md,
    backgroundColor: tokens.colors.bg.level1,
    borderRadius: tokens.borderRadius.sm,
    border: `1px solid ${tokens.colors.border.medium}`,
    fontSize: tokens.typography.fontSize.xs,
  },

  section: {
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacing.xs,
  },

  progressLabel: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: tokens.spacing.xs,
  },

  progressPercent: {
    fontWeight: tokens.typography.fontWeight.semibold,
    color: tokens.colors.text.primary,
    fontSize: tokens.typography.fontSize.sm,
  },

  progressBarOuter: {
    width: '100%',
    height: '6px',
    backgroundColor: tokens.colors.border.light,
    borderRadius: tokens.borderRadius.sm,
    overflow: 'hidden',
  },

  progressBarInner: {
    height: '100%',
    transition: `width ${tokens.transitions.stateChange}`,
    borderRadius: tokens.borderRadius.sm,
  },

  chunkInfo: {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacing.sm,
  },

  chunkCount: {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacing.xs,
  },

  chunkPercentage: {
    color: tokens.colors.text.secondary,
    fontSize: tokens.typography.fontSize.xs,
  },

  label: {
    color: tokens.colors.text.secondary,
    fontWeight: tokens.typography.fontWeight.medium,
  },

  value: {
    color: tokens.colors.text.primary,
    fontWeight: tokens.typography.fontWeight.semibold,
  },

  bufferHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },

  bufferBadge: {
    padding: '2px 8px',
    borderRadius: tokens.borderRadius.sm,
    fontSize: tokens.typography.fontSize.xs,
    fontWeight: tokens.typography.fontWeight.semibold,
  },

  bufferBar: {
    width: '100%',
    height: '4px',
    backgroundColor: tokens.colors.border.light,
    borderRadius: tokens.borderRadius.sm,
    overflow: 'hidden',
    marginBottom: tokens.spacing.xs,
  },

  bufferFill: {
    height: '100%',
    transition: `width ${tokens.transitions.hover}`,
    borderRadius: tokens.borderRadius.sm,
  },

  bufferDetails: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: tokens.spacing.sm,
    paddingTop: tokens.spacing.xs,
  },

  bufferMetric: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '4px 8px',
    backgroundColor: tokens.colors.bg.level2,
    borderRadius: tokens.borderRadius.sm,
  },

  metricLabel: {
    color: tokens.colors.text.secondary,
    fontSize: tokens.typography.fontSize.xs,
  },

  timeInfo: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))',
    gap: tokens.spacing.sm,
  },

  timeItem: {
    display: 'flex',
    flexDirection: 'column',
    gap: '2px',
    padding: '8px',
    backgroundColor: tokens.colors.bg.level2,
    borderRadius: tokens.borderRadius.sm,
  },

  speedInfo: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '8px',
    backgroundColor: tokens.colors.bg.level2,
    borderRadius: tokens.borderRadius.sm,
  },

  gaugeSection: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
    paddingTop: tokens.spacing.xs,
    borderTop: `1px solid ${tokens.colors.border.light}`,
  },

  gaugeContainer: {
    display: 'flex',
    gap: '4px',
  },

  gaugeMark: {
    flex: 1,
    height: '8px',
    borderRadius: tokens.borderRadius.sm,
    transition: tokens.transitions.background,
    backgroundColor: tokens.colors.border.light,
  },

  gaugeLabels: {
    display: 'flex',
    justifyContent: 'space-between',
    // #3639: bump to xs (11px) — WCAG AA body-text floor.
    fontSize: tokens.typography.fontSize.xs,
    color: tokens.colors.text.secondary,
  },
};
