/**
 * ProgressBar component styles using design tokens
 */

import type { CSSProperties } from 'react';
import { tokens } from '@/design-system';

export const progressBarStyles = {
  wrapper: {
    position: 'relative',
    width: '100%',
  } as CSSProperties,

  srOnly: {
    position: 'absolute',
    width: '1px',
    height: '1px',
    overflow: 'hidden',
    clip: 'rect(0,0,0,0)',
    whiteSpace: 'nowrap',
  } as CSSProperties,

  track: {
    position: 'absolute',
    top: '50%',
    transform: 'translateY(-50%)',
    width: '100%',
    height: '6px',
    backgroundColor: tokens.colors.bg.tertiary,
    borderRadius: tokens.borderRadius.full,
    overflow: 'hidden',
    boxShadow: `inset 0 1px 3px ${tokens.colors.opacityScale.dark.standard}`,
  } as CSSProperties,

  bufferedRange: (percentage: number, isDragging: boolean): CSSProperties => ({
    position: 'absolute',
    height: '100%',
    width: `${percentage}%`,
    backgroundColor: tokens.colors.accent.secondary,
    opacity: 0.4,
    transition: isDragging ? 'none' : 'width 0.1s ease-out',
  }),

  playedRange: (percentage: number, isDragging: boolean): CSSProperties => ({
    position: 'absolute',
    height: '100%',
    width: `${percentage}%`,
    background: tokens.gradients.aurora,
    transition: isDragging ? 'none' : 'width 0.1s ease-out',
  }),

  thumb: (percentage: number, isDragging: boolean): CSSProperties => ({
    position: 'absolute',
    top: '50%',
    left: `${percentage}%`,
    transform: 'translate(-50%, -50%)',
    width: isDragging ? '16px' : '12px',
    height: isDragging ? '16px' : '12px',
    backgroundColor: tokens.colors.accent.primary,
    borderRadius: '50%',
    boxShadow: isDragging ? tokens.shadows.glowMd : tokens.shadows.glowSoft,
    transition: 'all 0.1s ease-out',
    pointerEvents: 'none',
    border: `2px solid ${tokens.colors.bg.level1}`,
  }),

  container: (disabled: boolean, isFocused: boolean): CSSProperties => ({
    position: 'relative',
    height: '24px',
    cursor: disabled ? 'default' : 'pointer',
    padding: '8px 0',
    userSelect: 'none',
    outline: 'none',
    borderRadius: tokens.borderRadius.md,
    transition: isFocused && !disabled ? '0.2s outline' : 'none',
    ...(isFocused && !disabled && {
      outline: `3px solid ${tokens.colors.accent.primary}`,
      outlineOffset: '2px',
    }),
  }),

  tooltip: (hoverPercentage: number): CSSProperties => ({
    position: 'absolute',
    top: '-40px',
    left: `${Math.min(Math.max(hoverPercentage, 0), 100)}%`,
    transform: 'translateX(-50%)',
    backgroundColor: tokens.colors.bg.secondary,
    color: tokens.colors.text.primary,
    padding: `${tokens.spacing.sm} ${tokens.spacing.md}`,
    borderRadius: tokens.borderRadius.md,
    fontSize: tokens.typography.fontSize.xs,
    fontFamily: tokens.typography.fontFamily.mono,
    fontWeight: tokens.typography.fontWeight.semibold,
    whiteSpace: 'nowrap',
    pointerEvents: 'none',
    border: `1px solid ${tokens.colors.accent.primary}`,
    boxShadow: tokens.shadows.md,
    zIndex: tokens.zIndex.dropdown,
  }),
};
