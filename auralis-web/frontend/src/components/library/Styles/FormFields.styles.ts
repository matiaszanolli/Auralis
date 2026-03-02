/**
 * Form Field Styles - Reusable TextField styling for forms
 *
 * Consolidates TextField styling patterns across metadata forms, search bars,
 * and other input components. Provides consistent dark-themed input field styling
 * with multiple variants for different contexts.
 *
 * Variants:
 * - StyledTextField: Base form input (metadata, dialogs)
 * - SearchTextField: Search field with rounded pill shape
 * - CompactTextField: Minimal form input for space-constrained layouts
 */

import { TextField, styled } from '@mui/material';
import { tokens } from '@/design-system';

/**
 * StyledTextField - Base styled TextField for dark theme
 * Used in metadata forms, dialog inputs, and general form fields
 * Features: simple border styling, aurora focus color
 */
export const StyledTextField = styled(TextField)({
  '& .MuiOutlinedInput-root': {
    color: tokens.colors.text.primary,
    '& fieldset': { borderColor: tokens.colors.opacityScale.accent.light },
    '&:hover fieldset': { borderColor: tokens.colors.opacityScale.accent.standard },
    '&.Mui-focused fieldset': { borderColor: tokens.colors.accent.primary }
  },
  '& .MuiInputLabel-root': { color: tokens.colors.opacityScale.accent.standard }
});

/**
 * SearchTextField - Flat search field with minimal underline
 * Used in search bars and search interfaces
 * Features: transparent background, simple underline, minimal styling
 */
export const SearchTextField = styled(TextField)(({ theme: _theme }) => ({
  '& .MuiOutlinedInput-root': {
    height: tokens.components.searchBar.height,
    borderRadius: 0,
    background: 'transparent',
    border: 'none',
    borderBottom: `1px solid ${tokens.colors.border.light}`,
    transition: 'border-color 0.15s ease',
    paddingRight: tokens.spacing.sm,

    '& fieldset': {
      border: 'none',
    },

    '&:hover': {
      background: 'transparent',
      borderBottom: `1px solid ${tokens.colors.border.medium}`,
    },

    '&.Mui-focused': {
      background: 'transparent',
      borderBottom: `1px solid ${tokens.colors.accent.primary}`,
      boxShadow: 'none',
    },
  },

  '& .MuiOutlinedInput-input': {
    fontSize: tokens.typography.fontSize.md,
    color: tokens.colors.text.primary,
    padding: `${tokens.spacing.xs} ${tokens.spacing.md}`,

    '&::placeholder': {
      color: tokens.colors.text.tertiary,
      opacity: 0.7,
    },
  },

  '& .MuiInputAdornment-root': {
    marginRight: tokens.spacing.sm,
    color: tokens.colors.text.tertiary,
    opacity: 0.6,
  },
}));

/**
 * CompactTextField - Minimal form input for space-constrained layouts
 * Used in compact forms, inline editing, or mobile layouts
 * Features: reduced padding, minimal borders, dense styling
 */
export const CompactTextField = styled(TextField)(({ theme: _theme }) => ({
  '& .MuiOutlinedInput-root': {
    fontSize: tokens.typography.fontSize.sm,
    color: tokens.colors.text.primary,
    '& fieldset': { borderColor: tokens.colors.opacityScale.accent.ultraLight },
    '&:hover fieldset': { borderColor: tokens.colors.opacityScale.accent.lighter },
    '&.Mui-focused fieldset': { borderColor: tokens.colors.accent.primary }
  },
  '& .MuiOutlinedInput-input': {
    padding: `${tokens.spacing.xs} ${tokens.spacing.sm}`,
  },
  '& .MuiInputLabel-root': {
    color: tokens.colors.opacityScale.accent.lighter,
    fontSize: tokens.typography.fontSize.sm
  }
}));

export default StyledTextField;
