import type { TypographyVariantsOptions } from '@mui/material/styles';
import { tokens } from '@/design-system';
import type { SemanticTheme } from './semanticTheme';

/** MUI typography scale. Split out of themeConfig.ts (#5841). */
export const createTypography = (semantic: SemanticTheme): TypographyVariantsOptions => (
    {
      fontFamily: tokens.typography.fontFamily.primary,
      h1: {
        fontSize: tokens.typography.fontSize['3xl'],
        fontWeight: tokens.typography.fontWeight.bold,
        letterSpacing: '-0.5px',
      },
      h2: {
        fontSize: tokens.typography.fontSize.xl,
        fontWeight: tokens.typography.fontWeight.semibold,
        letterSpacing: '-0.25px',
      },
      h3: {
        fontSize: tokens.typography.fontSize.lg,
        fontWeight: tokens.typography.fontWeight.semibold,
      },
      h4: {
        fontSize: tokens.typography.fontSize.lg,
        fontWeight: tokens.typography.fontWeight.semibold,
      },
      body1: {
        fontSize: tokens.typography.fontSize.md,
        lineHeight: tokens.typography.lineHeight.normal,
      },
      body2: {
        fontSize: tokens.typography.fontSize.base,
        lineHeight: tokens.typography.lineHeight.normal,
      },
      caption: {
        fontSize: tokens.typography.fontSize.xs,
        color: semantic.textSecondary,
        letterSpacing: '0.5px',
      },
      button: {
        textTransform: 'none',
        fontWeight: tokens.typography.fontWeight.semibold,
      },
    });
