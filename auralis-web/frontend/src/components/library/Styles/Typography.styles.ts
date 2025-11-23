/**
 * Typography Styles - Reusable text and typography components
 *
 * Consolidates common text styling patterns for headers, labels, descriptions,
 * and other typography elements used across the application.
 *
 * Variants:
 * - SectionLabel: Section header typography (bold)
 * - SectionDescription: Secondary section text (dimmed)
 * - CategoryHeader: Section category header (uppercase, small)
 * - ResultTitle: Search result title
 * - ResultSubtitle: Search result metadata
 * - SmallText: Compact text for dense UI
 * - SecondaryText: Dimmed secondary text
 */

import { Typography, styled } from '@mui/material';

/**
 * SectionLabel - Section header typography
 * Used for: form section titles, dialog section headers
 * Features: bold weight, primary color, margin-bottom
 */
export const SectionLabel = styled(Typography)(({ theme }) => ({
  fontSize: '0.875rem',
  fontWeight: 600,
  color: theme.palette.text.primary,
  marginBottom: theme.spacing(1),
}));

/**
 * SectionDescription - Secondary section text
 * Used for: form section descriptions, helper text
 * Features: dimmed color, small font, reduced margin
 */
export const SectionDescription = styled(Typography)(({ theme }) => ({
  fontSize: '0.75rem',
  color: theme.palette.text.secondary,
  marginTop: theme.spacing(0.5),
}));

/**
 * CategoryHeader - Section category header with uppercase styling
 * Used for: search results category headers, list section headers
 * Features: uppercase, bold, letter-spacing, padding
 */
export const CategoryHeader = styled(Typography)(({ theme }) => ({
  fontSize: '0.75rem',
  fontWeight: 'bold',
  textTransform: 'uppercase',
  color: theme.palette.text.secondary,
  padding: theme.spacing(2, 2, 1, 2),
  letterSpacing: 1,
}));

/**
 * ResultTitle - Search result item title
 * Used for: search results, list item titles
 * Features: medium weight, smooth color transition
 */
export const ResultTitle = styled(Typography)({
  fontSize: '0.95rem',
  fontWeight: 500,
  transition: 'color 0.2s ease',
});

/**
 * ResultSubtitle - Search result item metadata
 * Used for: search results secondary info, artist/album info
 * Features: dimmed color, slightly smaller font
 */
export const ResultSubtitle = styled(Typography)(({ theme }) => ({
  fontSize: '0.85rem',
  color: theme.palette.text.secondary,
}));

/**
 * SmallText - Compact text for dense UI
 * Used for: metadata, timestamps, utility text
 * Features: small font, secondary color
 */
export const SmallText = styled(Typography)(({ theme }) => ({
  fontSize: '0.75rem',
  color: theme.palette.text.secondary,
  fontWeight: 400,
}));

/**
 * SecondaryText - Dimmed secondary text
 * Used for: inactive elements, helper text, disabled state
 * Features: disabled color, normal weight
 */
export const SecondaryText = styled(Typography)(({ theme }) => ({
  color: theme.palette.text.secondary,
  fontSize: '0.875rem',
  fontWeight: 400,
}));

/**
 * HelperText - Small helper or hint text
 * Used for: form helper text, tooltips, hints
 * Features: very small, disabled color, reduced line height
 */
export const HelperText = styled(Typography)(({ theme }) => ({
  fontSize: '0.7rem',
  color: theme.palette.text.disabled,
  lineHeight: 1.3,
}));
